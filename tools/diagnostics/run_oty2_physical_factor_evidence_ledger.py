"""Build the OTY2 physical-factor evidence ledger.

This is a posthoc mechanism-modeling report builder. It may read SAR GT,
SAR images, review anchors, and previously generated posthoc reports, but only
to label evidence provenance. It does not construct runtime priors, emit
annotation proposals, score candidates, rank/select boxes, train/tune
thresholds, or claim identity truth.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping, Sequence

from PIL import Image, ImageStat


REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = REPO_ROOT / "reports" / "oty2"
DOCS_DIR = REPO_ROOT / "docs"
DATA_ROOT = Path(r"D:\profile\research\data")
WORKSPACE_LOG_DIR = Path(r"D:\profile\research\workspace\logs")

FAN_CENTER_X = 1154.0
FAN_CENTER_Y = 1330.6

PROVENANCE_LABELS = [
    "runtime_safe_optical_evidence",
    "runtime_safe_temporal_evidence",
    "runtime_safe_geometry_or_vehicle_physics",
    "SAR_image_observation",
    "SAR_temporal_observation",
    "SAR_GT_posthoc_evidence",
    "manual_or_review_anchor",
    "similar_imaging_reference_only",
    "hypothesis_to_validate",
    "not_supported_or_insufficient",
]

BOUNDARY_FLAGS = {
    "posthoc_sar_gt_used": True,
    "posthoc_sar_image_content_used": True,
    "gt_or_sar_image_used_for_runtime_prior_construction": False,
    "runtime_prior_construction_used_gt": False,
    "annotation_proposal_entered": False,
    "training_or_threshold_tuning_entered": False,
    "candidate_box_scoring_output": False,
    "selector_or_ranking_used": False,
    "identity_truth_claimed": False,
    "model_weights_committed": False,
    "detection_dropout_rows_mixed_into_clean_paired": False,
    "gm011_missing_object_stream_rows_mixed_into_correspondence": False,
    "sar_only_rows_mixed_into_optical_sar_correspondence": False,
}

EXPECTED_LEDGER = {
    "paired_optical_object_sar_gt": 215,
    "blocked_missing_gm011_object_stream": 195,
    "sar_only_gt": 20,
    "no_oty_iou_match": 12,
}

TAXONOMY_FIELDS = [
    "factor_family",
    "factor_name",
    "model_layer",
    "evidence_scope",
    "provenance_labels",
    "current_support_level",
    "evidence_summary",
    "runtime_safe_path",
    "posthoc_limit",
    "blocker_or_next_action",
]

JOINT_PROBE_FIELDS = [
    "probe_id",
    "factor_combination",
    "sample_pool",
    "n_samples",
    "provenance_labels",
    "evidence_summary",
    "joint_result",
    "limits",
    "next_action",
    "guardrail_note",
]

OBJECT_LEDGER_FIELDS = [
    "scene",
    "object_hypothesis_id",
    "n_paired_frames",
    "optical_frame_span",
    "sar_frame_span",
    "vehicle_research_eligibility_modes",
    "context_modes",
    "azimuth_pass_rate",
    "size_shell_pass_rate",
    "range_shell_pass_rate",
    "area_vs_radius_trend",
    "height_vs_radius_trend",
    "bottom_y_vs_radius_trend",
    "center_x_vs_azimuth_trend",
    "trajectory_reliability_label",
    "paired_sar_peak_to_background_median",
    "paired_sar_box_to_background_median",
    "paired_sar_center_to_peak_distance_median",
    "sar_local_peak_drift_label",
    "state_conditioned_uncertainty",
    "recommended_use",
    "review_need",
    "provenance_labels",
    "notes",
]

SAR_TEMPORAL_FIELDS = [
    "sample_pool",
    "scene",
    "object_hypothesis_id",
    "n_samples",
    "optical_frame_span",
    "sar_frame_span",
    "sar_gt_ids_sample",
    "sar_gt_center_x_slope_per_sar_frame",
    "sar_gt_center_y_slope_per_sar_frame",
    "sar_peak_x_slope_per_sar_frame",
    "sar_peak_y_slope_per_sar_frame",
    "sar_centroid_x_slope_per_sar_frame",
    "sar_centroid_y_slope_per_sar_frame",
    "peak_to_background_median",
    "box_to_background_median",
    "center_to_peak_distance_median",
    "gt_center_vs_peak_drift_label",
    "temporal_support_summary",
    "provenance_labels",
    "notes",
]

MANUAL_REVIEW_FIELDS = [
    "priority",
    "scene",
    "object_hypothesis_id",
    "sample_pool",
    "optical_frame_span",
    "sar_frame_span",
    "n_samples",
    "review_need",
    "reason",
    "mechanism_relevance",
    "required_inputs",
    "not_identity_truth_note",
    "provenance_labels",
]


def latest_path(pattern: str, base_dir: Path = REPORT_DIR) -> Path:
    paths = sorted(base_dir.glob(pattern))
    if not paths:
        raise FileNotFoundError(f"No file matched {base_dir / pattern}")
    return paths[-1]


def latest_stratified_data_csv() -> Path:
    paths = [
        path
        for path in REPORT_DIR.glob("oty2_gt_mechanism_stratified_validation_*.csv")
        if "visual_summary" not in path.name
    ]
    if not paths:
        raise FileNotFoundError("No stratified validation data CSV found")
    return sorted(paths)[-1]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def write_json(path: Path, data: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def safe_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(result) or math.isinf(result):
        return None
    return result


def safe_int(value: Any) -> int | None:
    number = safe_float(value)
    if number is None:
        return None
    return int(round(number))


def fmt(value: Any, digits: int = 4) -> str:
    number = safe_float(value)
    if number is None:
        return ""
    text = f"{number:.{digits}f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


def bool_rate(rows: Sequence[Mapping[str, Any]], field: str) -> str:
    if not rows:
        return ""
    passed = sum(1 for row in rows if str(row.get(field, "")).lower() == "true")
    return fmt(passed / len(rows), 4)


def median_clean(values: Iterable[Any]) -> float | None:
    clean = [float(value) for value in (safe_float(item) for item in values) if value is not None]
    return float(median(clean)) if clean else None


def compact_counts(values: Iterable[Any], limit: int = 8) -> str:
    counter = Counter(str(value) for value in values if str(value) != "")
    return ";".join(f"{key}={count}" for key, count in counter.most_common(limit))


def frame_span(rows: Sequence[Mapping[str, Any]], field: str) -> str:
    values = [safe_int(row.get(field)) for row in rows]
    clean = sorted(value for value in values if value is not None)
    if not clean:
        return ""
    if clean[0] == clean[-1]:
        return str(clean[0])
    return f"{clean[0]}-{clean[-1]}"


def sample_values(rows: Sequence[Mapping[str, Any]], field: str, limit: int = 6) -> str:
    values: list[str] = []
    for row in rows:
        value = str(row.get(field, ""))
        if value and value not in values:
            values.append(value)
        if len(values) >= limit:
            break
    return ";".join(values)


def parse_center(text: str) -> tuple[float, float] | None:
    parts = [safe_float(part.strip()) for part in str(text).split(",")]
    if len(parts) < 2 or parts[0] is None or parts[1] is None:
        return None
    return float(parts[0]), float(parts[1])


def parse_wh(text: str) -> tuple[float, float] | None:
    w_match = re.search(r"w=([-+]?\d+(?:\.\d+)?)", text or "")
    h_match = re.search(r"h=([-+]?\d+(?:\.\d+)?)", text or "")
    if not w_match or not h_match:
        return None
    width = safe_float(w_match.group(1))
    height = safe_float(h_match.group(1))
    if width is None or height is None:
        return None
    return width, height


def slope(rows: Sequence[Mapping[str, Any]], x_field: str, y_field: str) -> float | None:
    pairs: list[tuple[float, float]] = []
    for row in rows:
        x_val = safe_float(row.get(x_field))
        y_val = safe_float(row.get(y_field))
        if x_val is not None and y_val is not None:
            pairs.append((x_val, y_val))
    if len(pairs) < 2:
        return None
    x_mean = sum(x for x, _ in pairs) / len(pairs)
    y_mean = sum(y for _, y in pairs) / len(pairs)
    denominator = sum((x - x_mean) ** 2 for x, _ in pairs)
    if abs(denominator) < 1e-12:
        return None
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in pairs)
    return numerator / denominator


def direction(value: Any, eps: float = 0.05) -> int:
    number = safe_float(value)
    if number is None or abs(number) <= eps:
        return 0
    return 1 if number > 0 else -1


def drift_label(rows: Sequence[Mapping[str, Any]]) -> str:
    if len(rows) < 3:
        return "insufficient_sar_temporal_samples"
    gt_x = slope(rows, "sar_frame", "sar_gt_center_x")
    gt_y = slope(rows, "sar_frame", "sar_gt_center_y")
    peak_x = slope(rows, "sar_frame", "sar_peak_x")
    peak_y = slope(rows, "sar_frame", "sar_peak_y")
    if peak_x is None and peak_y is None:
        return "local_peak_coordinates_insufficient"
    comparisons: list[bool] = []
    for gt_value, peak_value in ((gt_x, peak_x), (gt_y, peak_y)):
        gt_dir = direction(gt_value)
        peak_dir = direction(peak_value)
        if gt_dir and peak_dir:
            comparisons.append(gt_dir == peak_dir)
    if comparisons and all(comparisons):
        return "local_peak_drift_consistent_with_sar_gt_center_posthoc"
    if comparisons and not any(comparisons):
        return "local_peak_drift_conflicts_with_sar_gt_center_posthoc"
    return "local_peak_drift_partial_or_axis_weak_posthoc"


def sar_image_path(scene: str, frame: int) -> Path:
    return DATA_ROOT / scene / f"{scene}_SARframes" / f"{frame:06d}.png"


def scatter_stats(image_path: Path, cx: float, cy: float, width: float, height: float) -> dict[str, Any]:
    if not image_path.exists():
        return {"sar_image_read_status": "missing"}
    try:
        with Image.open(image_path) as source:
            gray = source.convert("L")
            x1 = max(0, int(math.floor(cx - width / 2.0)))
            y1 = max(0, int(math.floor(cy - height / 2.0)))
            x2 = min(gray.width, int(math.ceil(cx + width / 2.0)))
            y2 = min(gray.height, int(math.ceil(cy + height / 2.0)))
            if x2 <= x1 or y2 <= y1:
                return {"sar_image_read_status": "empty_gt_box"}
            box = gray.crop((x1, y1, x2, y2))
            values = list(box.getdata())
            stat = ImageStat.Stat(box)
            max_value = float(max(values)) if values else 0.0
            max_index = values.index(int(max_value)) if values else 0
            crop_width = max(1, x2 - x1)
            peak_x = x1 + (max_index % crop_width)
            peak_y = y1 + (max_index // crop_width)
            sorted_values = sorted(values)
            top_count = max(1, int(len(sorted_values) * 0.05))
            threshold = sorted_values[-top_count]
            weighted_x = 0.0
            weighted_y = 0.0
            weight_sum = 0.0
            for index, raw_value in enumerate(values):
                if raw_value < threshold:
                    continue
                px = x1 + (index % crop_width)
                py = y1 + (index // crop_width)
                weight = float(raw_value)
                weighted_x += px * weight
                weighted_y += py * weight
                weight_sum += weight
            centroid_x = weighted_x / weight_sum if weight_sum else float(peak_x)
            centroid_y = weighted_y / weight_sum if weight_sum else float(peak_y)
            pad = 20
            bx1 = max(0, x1 - pad)
            by1 = max(0, y1 - pad)
            bx2 = min(gray.width, x2 + pad)
            by2 = min(gray.height, y2 + pad)
            bg = gray.crop((bx1, by1, bx2, by2))
            bg_stat = ImageStat.Stat(bg)
            box_mean = float(stat.mean[0]) if stat.mean else 0.0
            bg_mean = float(bg_stat.mean[0]) if bg_stat.mean else 0.0
            top5 = sorted_values[-top_count:]
            top5_mean = sum(top5) / len(top5) if top5 else max_value
            return {
                "sar_image_read_status": "ok",
                "sar_box_mean_intensity": box_mean / 255.0,
                "sar_box_max_intensity": max_value / 255.0,
                "sar_box_top5_mean_intensity": top5_mean / 255.0,
                "sar_local_background_mean": bg_mean / 255.0,
                "sar_box_to_background_ratio": box_mean / max(bg_mean, 1e-6),
                "sar_peak_to_background_ratio": max_value / max(bg_mean, 1e-6),
                "sar_peak_x": float(peak_x),
                "sar_peak_y": float(peak_y),
                "sar_centroid_x": centroid_x,
                "sar_centroid_y": centroid_y,
                "sar_center_to_peak_distance_px": math.hypot(float(peak_x) - cx, float(peak_y) - cy),
                "sar_center_to_centroid_distance_px": math.hypot(centroid_x - cx, centroid_y - cy),
            }
    except OSError as exc:
        return {"sar_image_read_status": f"read_error:{exc}"}


def build_paired_scatter_records(correspondence_rows: Sequence[Mapping[str, str]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in correspondence_rows:
        center = parse_center(str(row.get("sar_gt_center", "")))
        wh = parse_wh(str(row.get("sar_gt_width_height_or_rotated_box", "")))
        frame = safe_int(row.get("sar_frame"))
        scene = str(row.get("scene", ""))
        if center is None or wh is None or frame is None:
            continue
        cx, cy = center
        width, height = wh
        stats = scatter_stats(sar_image_path(scene, frame), cx, cy, width, height)
        record: dict[str, Any] = {
            "scene": scene,
            "object_hypothesis_id": row.get("object_hypothesis_id", ""),
            "sar_gt_id": row.get("sar_gt_id", ""),
            "sar_frame": row.get("sar_frame", ""),
            "optical_frame": row.get("optical_frame", ""),
            "sar_gt_center_x": cx,
            "sar_gt_center_y": cy,
        }
        record.update(stats)
        records.append(record)
    return records


def load_inputs(args: argparse.Namespace) -> dict[str, Any]:
    paths = {
        "stratified_summary_json": Path(args.stratified_summary_json) if args.stratified_summary_json else latest_path("oty2_gt_mechanism_stratified_validation_summary_*.json"),
        "stratified_csv": Path(args.stratified_csv) if args.stratified_csv else latest_stratified_data_csv(),
        "azimuth_csv": Path(args.azimuth_csv) if args.azimuth_csv else latest_path("oty2_azimuth_margin_ablation_*.csv"),
        "shell_csv": Path(args.shell_csv) if args.shell_csv else latest_path("oty2_vehicle_shell_ablation_*.csv"),
        "shape_csv": Path(args.shape_csv) if args.shape_csv else latest_path("oty2_optical_shape_range_stratified_probe_*.csv"),
        "temporal_csv": Path(args.temporal_csv) if args.temporal_csv else latest_path("oty2_temporal_trajectory_mechanism_probe_*.csv"),
        "sar_only_csv": Path(args.sar_only_csv) if args.sar_only_csv else latest_path("oty2_sar_only_morphology_reference_*.csv"),
        "correspondence_csv": Path(args.correspondence_csv) if args.correspondence_csv else latest_path("oty2_gt_correspondence_mechanism_audit_*.csv"),
        "correspondence_summary_json": Path(args.correspondence_summary_json) if args.correspondence_summary_json else latest_path("oty2_gt_correspondence_mechanism_summary_*.json"),
        "dropout_temporal_csv": Path(args.dropout_temporal_csv) if args.dropout_temporal_csv else latest_path("oty2_detection_dropout_temporal_support_audit_*.csv"),
        "dropout_sar_csv": Path(args.dropout_sar_csv) if args.dropout_sar_csv else latest_path("oty2_detection_dropout_sar_posthoc_support_audit_*.csv"),
        "accounting_csv": Path(args.accounting_csv) if args.accounting_csv else latest_path("oty2_gt_sample_accounting_audit_*.csv"),
    }
    with paths["stratified_summary_json"].open("r", encoding="utf-8") as handle:
        stratified_summary = json.load(handle)
    with paths["correspondence_summary_json"].open("r", encoding="utf-8") as handle:
        correspondence_summary = json.load(handle)
    return {
        "paths": paths,
        "stratified_summary": stratified_summary,
        "correspondence_summary": correspondence_summary,
        "stratified_rows": read_csv(paths["stratified_csv"]),
        "azimuth_rows": read_csv(paths["azimuth_csv"]),
        "shell_rows": read_csv(paths["shell_csv"]),
        "shape_rows": read_csv(paths["shape_csv"]),
        "temporal_rows": read_csv(paths["temporal_csv"]),
        "sar_only_rows": read_csv(paths["sar_only_csv"]),
        "correspondence_rows": read_csv(paths["correspondence_csv"]),
        "dropout_temporal_rows": read_csv(paths["dropout_temporal_csv"]),
        "dropout_sar_rows": read_csv(paths["dropout_sar_csv"]),
        "accounting_rows": read_csv(paths["accounting_csv"]),
    }


def validate_ledger(summary: Mapping[str, Any]) -> dict[str, Any]:
    ledger = dict(summary.get("sample_ledger", {}))
    counts = dict(ledger.get("category_counts", {}))
    expected_ok = all(int(counts.get(key, -1)) == value for key, value in EXPECTED_LEDGER.items())
    if not ledger.get("ledger_valid") or not expected_ok:
        raise RuntimeError(f"Ledger mismatch; stop before conclusions: {json.dumps(ledger, ensure_ascii=False)}")
    return ledger


def object_scatter_summary(paired_scatter_rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in paired_scatter_rows:
        key = f"{row.get('scene', '')}|{row.get('object_hypothesis_id', '')}"
        grouped[key].append(row)
    summaries: dict[str, dict[str, Any]] = {}
    for key, rows in grouped.items():
        ordered = sorted(rows, key=lambda item: safe_float(item.get("sar_frame")) or 0.0)
        summaries[key] = {
            "peak_to_background_median": median_clean(row.get("sar_peak_to_background_ratio") for row in ordered),
            "box_to_background_median": median_clean(row.get("sar_box_to_background_ratio") for row in ordered),
            "center_to_peak_distance_median": median_clean(row.get("sar_center_to_peak_distance_px") for row in ordered),
            "gt_center_x_slope": slope(ordered, "sar_frame", "sar_gt_center_x"),
            "gt_center_y_slope": slope(ordered, "sar_frame", "sar_gt_center_y"),
            "peak_x_slope": slope(ordered, "sar_frame", "sar_peak_x"),
            "peak_y_slope": slope(ordered, "sar_frame", "sar_peak_y"),
            "centroid_x_slope": slope(ordered, "sar_frame", "sar_centroid_x"),
            "centroid_y_slope": slope(ordered, "sar_frame", "sar_centroid_y"),
            "drift_label": drift_label(ordered),
            "records": ordered,
        }
    return summaries


def state_uncertainty(context_modes: str, reliability: str, n_frames: int) -> str:
    if n_frames < 3:
        return "high_uncertainty_sparse_object"
    risky = any(token in context_modes for token in ("edge", "duplicate_or_handoff", "ambiguous_or_review_only"))
    if risky or "review_only" in reliability:
        return "state_conditioned_uncertainty_required"
    if "clean_object_temporal_signal" in reliability:
        return "lower_uncertainty_clean_posthoc_probe"
    return "moderate_uncertainty_temporal_signal_only"


def review_need(scene: str, context_modes: str, reliability: str, n_frames: int, azimuth_rate: str) -> str:
    rate = safe_float(azimuth_rate)
    if scene == "GM_RM019":
        if n_frames < 3:
            return "GM_RM019 sparse object; optical GT / identity review recommended"
        if rate is not None and rate < 0.75:
            return "GM_RM019 low azimuth coverage; review object continuity and complete frames"
        if "ambiguous_or_review_only" in context_modes or "edge" in context_modes:
            return "GM_RM019 state-mixed trajectory; review complete morphology frames"
        return "GM_RM019 light identity/continuity review before generalization"
    if "review_only_temporal_signal" in reliability or "duplicate_or_handoff" in context_modes:
        return "review-only/state-mixed object; keep as explanation evidence unless reviewed"
    return "none_for_current_posthoc_report"


def build_object_ledger(
    temporal_rows: Sequence[Mapping[str, str]],
    correspondence_rows: Sequence[Mapping[str, str]],
    scatter_by_object: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, str]]] = defaultdict(list)
    for row in correspondence_rows:
        key = f"{row.get('scene', '')}|{row.get('object_hypothesis_id', '')}"
        grouped[key].append(row)

    rows: list[dict[str, Any]] = []
    for temporal in temporal_rows:
        scene = str(temporal.get("scene", ""))
        object_id = str(temporal.get("object_hypothesis_id", ""))
        key = f"{scene}|{object_id}"
        corr = grouped.get(key, [])
        scatter = scatter_by_object.get(key, {})
        n_frames = safe_int(temporal.get("n_paired_frames")) or len(corr)
        azimuth_rate = bool_rate(corr, "azimuth_prior_contains_gt")
        size_rate = bool_rate(corr, "vehicle_size_shell_contains_gt")
        range_rate = bool_rate(corr, "range_shell_contains_gt")
        reliability = str(temporal.get("trajectory_reliability_label", ""))
        context_modes = str(temporal.get("context_modes", ""))
        uncertainty = state_uncertainty(context_modes, reliability, n_frames)
        need = review_need(scene, context_modes, reliability, n_frames, azimuth_rate)
        recommended = "object_level_hypothesis_to_validate"
        if "clean_object_temporal_signal" in reliability:
            recommended = "cleaner_object_level_probe_candidate_posthoc_only"
        elif "review_only" in reliability or "state_conditioned" in uncertainty:
            recommended = "review_or_state_conditioned_evidence_only"
        if n_frames < 3:
            recommended = "insufficient_for_object_trend"
        rows.append(
            {
                "scene": scene,
                "object_hypothesis_id": object_id,
                "n_paired_frames": str(n_frames),
                "optical_frame_span": frame_span(corr, "optical_frame"),
                "sar_frame_span": frame_span(corr, "sar_frame"),
                "vehicle_research_eligibility_modes": temporal.get("vehicle_research_eligibility_modes", ""),
                "context_modes": context_modes,
                "azimuth_pass_rate": azimuth_rate,
                "size_shell_pass_rate": size_rate,
                "range_shell_pass_rate": range_rate,
                "area_vs_radius_trend": temporal.get("area_vs_radius_trend", ""),
                "height_vs_radius_trend": temporal.get("height_vs_radius_trend", ""),
                "bottom_y_vs_radius_trend": temporal.get("bottom_y_vs_radius_trend", ""),
                "center_x_vs_azimuth_trend": temporal.get("center_x_vs_azimuth_trend", ""),
                "trajectory_reliability_label": reliability,
                "paired_sar_peak_to_background_median": fmt(scatter.get("peak_to_background_median"), 4),
                "paired_sar_box_to_background_median": fmt(scatter.get("box_to_background_median"), 4),
                "paired_sar_center_to_peak_distance_median": fmt(scatter.get("center_to_peak_distance_median"), 3),
                "sar_local_peak_drift_label": scatter.get("drift_label", ""),
                "state_conditioned_uncertainty": uncertainty,
                "recommended_use": recommended,
                "review_need": need,
                "provenance_labels": ";".join(
                    [
                        "runtime_safe_optical_evidence",
                        "runtime_safe_temporal_evidence",
                        "SAR_GT_posthoc_evidence",
                        "SAR_image_observation",
                        "hypothesis_to_validate",
                    ]
                ),
                "notes": "Object hypothesis is an optical object unit, not identity truth; SAR GT/image fields are posthoc evidence only.",
            }
        )
    return rows


def build_sar_temporal_probe(
    scatter_by_object: Mapping[str, Mapping[str, Any]],
    dropout_temporal_rows: Sequence[Mapping[str, str]],
    dropout_sar_rows: Sequence[Mapping[str, str]],
    sar_only_rows: Sequence[Mapping[str, str]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key, summary in sorted(scatter_by_object.items()):
        records = list(summary.get("records", []))
        if "|" in key:
            scene, object_id = key.split("|", 1)
        else:
            scene, object_id = "", key
        rows.append(
            {
                "sample_pool": "paired_optical_object_sar_gt",
                "scene": scene,
                "object_hypothesis_id": object_id,
                "n_samples": str(len(records)),
                "optical_frame_span": frame_span(records, "optical_frame"),
                "sar_frame_span": frame_span(records, "sar_frame"),
                "sar_gt_ids_sample": sample_values(records, "sar_gt_id"),
                "sar_gt_center_x_slope_per_sar_frame": fmt(summary.get("gt_center_x_slope"), 6),
                "sar_gt_center_y_slope_per_sar_frame": fmt(summary.get("gt_center_y_slope"), 6),
                "sar_peak_x_slope_per_sar_frame": fmt(summary.get("peak_x_slope"), 6),
                "sar_peak_y_slope_per_sar_frame": fmt(summary.get("peak_y_slope"), 6),
                "sar_centroid_x_slope_per_sar_frame": fmt(summary.get("centroid_x_slope"), 6),
                "sar_centroid_y_slope_per_sar_frame": fmt(summary.get("centroid_y_slope"), 6),
                "peak_to_background_median": fmt(summary.get("peak_to_background_median"), 4),
                "box_to_background_median": fmt(summary.get("box_to_background_median"), 4),
                "center_to_peak_distance_median": fmt(summary.get("center_to_peak_distance_median"), 3),
                "gt_center_vs_peak_drift_label": summary.get("drift_label", ""),
                "temporal_support_summary": "Local SAR peak/centroid drift computed inside posthoc SAR GT crop.",
                "provenance_labels": ";".join(["SAR_temporal_observation", "SAR_image_observation", "SAR_GT_posthoc_evidence"]),
                "notes": "Posthoc SAR temporal observation; not a runtime peak tracker or selector.",
            }
        )

    dropout_supported = sum(1 for row in dropout_temporal_rows if str(row.get("temporal_continuation_with_detection_dropout", "")).lower() == "true")
    dropout_sar_supported = sum(1 for row in dropout_sar_rows if row.get("sar_posthoc_support_status") == "sar_posthoc_supported_detection_dropout")
    rows.append(
        {
            "sample_pool": "detection_dropout_temporal_continuation",
            "scene": compact_counts(row.get("scene", "") for row in dropout_temporal_rows),
            "object_hypothesis_id": "",
            "n_samples": str(len(dropout_temporal_rows)),
            "optical_frame_span": frame_span(dropout_temporal_rows, "optical_frame"),
            "sar_frame_span": frame_span(dropout_temporal_rows, "sar_frame"),
            "sar_gt_ids_sample": sample_values(dropout_temporal_rows, "sar_gt_id"),
            "peak_to_background_median": fmt(median_clean(row.get("sar_peak_to_background_ratio") for row in dropout_sar_rows), 4),
            "box_to_background_median": fmt(median_clean(row.get("sar_box_to_background_ratio") for row in dropout_sar_rows), 4),
            "gt_center_vs_peak_drift_label": "dropout_pool_temporal_existence_support_not_clean_morphology",
            "temporal_support_summary": f"temporal_continuation={dropout_supported}/{len(dropout_temporal_rows)}; sar_posthoc_support={dropout_sar_supported}/{len(dropout_sar_rows)}",
            "provenance_labels": ";".join(
                [
                    "runtime_safe_temporal_evidence",
                    "SAR_temporal_observation",
                    "SAR_image_observation",
                    "SAR_GT_posthoc_evidence",
                    "manual_or_review_anchor",
                ]
            ),
            "notes": "Kept separate from clean paired morphology; propagation boxes are diagnostics only.",
        }
    )
    rows.append(
        {
            "sample_pool": "sar_only_gt_reference",
            "scene": compact_counts(row.get("scene", "") for row in sar_only_rows),
            "object_hypothesis_id": "",
            "n_samples": str(len(sar_only_rows)),
            "sar_frame_span": frame_span(sar_only_rows, "sar_frame"),
            "sar_gt_ids_sample": sample_values(sar_only_rows, "sar_gt_id"),
            "peak_to_background_median": fmt(median_clean(row.get("sar_peak_to_background_ratio") for row in sar_only_rows), 4),
            "box_to_background_median": fmt(median_clean(row.get("sar_box_to_background_ratio") for row in sar_only_rows), 4),
            "center_to_peak_distance_median": fmt(median_clean(row.get("sar_center_to_peak_distance_px") for row in sar_only_rows), 3),
            "gt_center_vs_peak_drift_label": "sar_only_reference_not_optical_correspondence",
            "temporal_support_summary": "SAR-only rows provide SAR morphology/scatter reference but no optical object trajectory.",
            "provenance_labels": ";".join(["SAR_image_observation", "SAR_GT_posthoc_evidence"]),
            "notes": "Excluded from optical-SAR correspondence statistics.",
        }
    )
    return rows


def row_by(rows: Sequence[Mapping[str, str]], **kwargs: str) -> Mapping[str, str]:
    for row in rows:
        if all(str(row.get(key, "")) == value for key, value in kwargs.items()):
            return row
    return {}


def build_taxonomy(
    summary: Mapping[str, Any],
    correspondence_summary: Mapping[str, Any],
    sar_temporal_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    ledger = summary["sample_ledger"]["category_counts"]
    frame = summary["frame_level"]
    temporal = summary["temporal_summary"]
    sar_only = summary["sar_only_summary"]
    paired_peak = correspondence_summary.get("scatter_peak_to_background_median")
    paired_box = correspondence_summary.get("scatter_box_to_background_median")
    dropout_row = next((row for row in sar_temporal_rows if row.get("sample_pool") == "detection_dropout_temporal_continuation"), {})
    return [
        {
            "factor_family": "F_time",
            "factor_name": "24fps optical to 50fps SAR software-sync temporal tube",
            "model_layer": "runtime-safe temporal support",
            "evidence_scope": f"paired temporal window pass={frame.get('temporal_window_pass_rate')}; dropout temporal support={dropout_row.get('temporal_support_summary', '')}",
            "provenance_labels": "runtime_safe_temporal_evidence;SAR_GT_posthoc_evidence;hypothesis_to_validate",
            "current_support_level": "strong_runtime_safe_contract_with_posthoc_validation",
            "evidence_summary": "Use the 50/24 scale as an object temporal tube, not one optical frame to one SAR frame timestamp truth.",
            "runtime_safe_path": "Available from acquisition fps and optical object stream before SAR GT.",
            "posthoc_limit": "GT validates window coverage only; it must not tune hidden offsets as a runtime prior.",
            "blocker_or_next_action": "Quantify jitter/state effects inside object-level temporal windows.",
        },
        {
            "factor_family": "F_az",
            "factor_name": "fan-polar / range-azimuth azimuth mapping",
            "model_layer": "runtime-safe geometry candidate",
            "evidence_scope": f"original paired coverage={summary['azimuth_key_results']['original_interval']['coverage_rate']}; GM_RM019 remains weak.",
            "provenance_labels": "runtime_safe_geometry_or_vehicle_physics;SAR_GT_posthoc_evidence;hypothesis_to_validate",
            "current_support_level": "state_and_scene_conditioned_posthoc_support",
            "evidence_summary": "Azimuth sectors cover most paired rows but require wide/state-aware uncertainty; GM_RM019 has low coverage.",
            "runtime_safe_path": "Can be generated from optical object state and scene geometry without SAR GT.",
            "posthoc_limit": "Coverage-vs-margin results are validation evidence, not selected runtime thresholds.",
            "blocker_or_next_action": "Review GM_RM019 trajectory/complete frames and scene-specific residuals.",
        },
        {
            "factor_family": "F_shell",
            "factor_name": "vehicle physical length/width footprint shell",
            "model_layer": "runtime-safe vehicle physics candidate",
            "evidence_scope": f"tight={summary['vehicle_shell_key_results']['tight_vehicle_shell']['coverage_rate']}; base={summary['vehicle_shell_key_results']['base_vehicle_shell']['coverage_rate']}; relaxed={summary['vehicle_shell_key_results']['relaxed_vehicle_shell']['coverage_rate']}",
            "provenance_labels": "runtime_safe_geometry_or_vehicle_physics;SAR_GT_posthoc_evidence;hypothesis_to_validate",
            "current_support_level": "promising_posthoc_compression",
            "evidence_summary": "Intersecting vehicle footprint with azimuth compresses angular support; tight shell misses 3 complete GM_RM017 rows.",
            "runtime_safe_path": "Vehicle size priors can be defined before GT, then validated posthoc.",
            "posthoc_limit": "Base/relaxed 100% coverage is conservative coverage, not precise localization proof.",
            "blocker_or_next_action": "Analyze tight misses and state-aware shell widening.",
        },
        {
            "factor_family": "F_range_shape",
            "factor_name": "optical bbox height / bottom_y / area vs SAR radius",
            "model_layer": "posthoc range-shape hypothesis",
            "evidence_scope": f"area={frame.get('area_radius_pearson')}; height={frame.get('height_radius_pearson')}; bottom_y={frame.get('bottom_y_radius_pearson')}; aspect={frame.get('aspect_radius_pearson')}",
            "provenance_labels": "runtime_safe_optical_evidence;SAR_GT_posthoc_evidence;hypothesis_to_validate",
            "current_support_level": "strong_frame_level_but_object_level_limited",
            "evidence_summary": "Height, bottom_y, and area show strong posthoc radius relations; aspect is unstable.",
            "runtime_safe_path": "Can only become runtime-safe after an independent range hypothesis is defined without GT.",
            "posthoc_limit": "Frame-level correlation is GM_RM017/repeated-frame dominated and not an object-level law.",
            "blocker_or_next_action": "Validate within complete objects and after GM_RM019/GM_RM011 data completion.",
        },
        {
            "factor_family": "F_traj",
            "factor_name": "optical object trajectory direction vs SAR GT trend",
            "model_layer": "object-level temporal hypothesis",
            "evidence_scope": f"trajectory reliability={json.dumps(temporal.get('trajectory_reliability_counts', {}), ensure_ascii=False)}",
            "provenance_labels": "runtime_safe_optical_evidence;runtime_safe_temporal_evidence;SAR_GT_posthoc_evidence;hypothesis_to_validate",
            "current_support_level": "review_context_support_not_identity_truth",
            "evidence_summary": "Object-level trend is useful, but only one object is currently clean; many rows are review/state-mixed.",
            "runtime_safe_path": "Optical object trajectories are runtime-safe; SAR GT trend is posthoc validation only.",
            "posthoc_limit": "Does not establish identity truth.",
            "blocker_or_next_action": "Manual review for GM_RM019 and state-mixed GM_RM017 objects.",
        },
        {
            "factor_family": "F_sar_image",
            "factor_name": "SAR local peak, box/background, peak/background, footprint axes",
            "model_layer": "SAR observation factor",
            "evidence_scope": f"paired peak/background median={fmt(paired_peak, 4)}; paired box/background median={fmt(paired_box, 4)}; SAR-only local peak supported={sar_only.get('scatter_support_counts', {}).get('local_scatter_peak_supported', 0)}/{sar_only.get('sample_count')}",
            "provenance_labels": "SAR_image_observation;SAR_GT_posthoc_evidence;hypothesis_to_validate",
            "current_support_level": "strong_sar_observation_posthoc_support",
            "evidence_summary": "Paired/SAR-only/dropout pools all show useful SAR-side local peak evidence, though box mean can be weak.",
            "runtime_safe_path": "Can be used by the final SAR observation stage inside an optical-derived support region.",
            "posthoc_limit": "GT-centered crop statistics are not runtime scoring rules.",
            "blocker_or_next_action": "Build non-GT SAR local evidence extraction inside runtime-safe support regions.",
        },
        {
            "factor_family": "F_sar_temporal",
            "factor_name": "SAR temporal scattering continuity",
            "model_layer": "SAR temporal observation factor",
            "evidence_scope": f"paired object rows={len([row for row in sar_temporal_rows if row.get('sample_pool') == 'paired_optical_object_sar_gt'])}; dropout={dropout_row.get('temporal_support_summary', '')}",
            "provenance_labels": "SAR_temporal_observation;SAR_image_observation;SAR_GT_posthoc_evidence;hypothesis_to_validate",
            "current_support_level": "promising_but_posthoc_quantification_needed",
            "evidence_summary": "SAR peak/centroid drift can be measured posthoc; dropout cases show strong temporal existence support.",
            "runtime_safe_path": "Use SAR image sequence inside temporal tube after optical prior construction.",
            "posthoc_limit": "Current local-peak drift is GT-crop based and cannot be used as a prior.",
            "blocker_or_next_action": "Replace GT-crop peak tracking with support-region peak tracking.",
        },
        {
            "factor_family": "F_state",
            "factor_name": "complete / truncated / edge / far-small / duplicate / dropout conditioned uncertainty",
            "model_layer": "uncertainty routing factor",
            "evidence_scope": f"paired status counts={frame.get('status_counts')}; dropout pool={ledger.get('no_oty_iou_match')}",
            "provenance_labels": "runtime_safe_optical_evidence;manual_or_review_anchor;hypothesis_to_validate",
            "current_support_level": "necessary_conditioning_factor",
            "evidence_summary": "State changes explain why a single global rule fails; dropout and SAR-only pools must remain separate.",
            "runtime_safe_path": "State can be inferred from optical object stream and review-only labels for audit.",
            "posthoc_limit": "Review labels are anchors, not runtime truth.",
            "blocker_or_next_action": "Formalize state-conditioned uncertainty without mixing pools.",
        },
        {
            "factor_family": "similar_imaging_reference",
            "factor_name": "MATLAB FMCW/SAR imaging toolbox concepts",
            "model_layer": "reference-only physical vocabulary",
            "evidence_scope": "range FFT, range-azimuth grid, BP focusing, mainlobe/sidelobe, IRW/PSLR/ISLR/ENL concepts",
            "provenance_labels": "similar_imaging_reference_only",
            "current_support_level": "reference_only_not_current_pipeline",
            "evidence_summary": "Useful to name SAR observation factors, but not evidence that the OTY2 images share the same raw-data pipeline.",
            "runtime_safe_path": "Only as vocabulary and diagnostic inspiration.",
            "posthoc_limit": "Do not import zip/toolbox code or assume parameters/axes/preprocessing match.",
            "blocker_or_next_action": "Any future reference implementation needs explicit path, source, and license planning.",
        },
    ]


def build_joint_probe_rows(
    summary: Mapping[str, Any],
    correspondence_summary: Mapping[str, Any],
    sar_temporal_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    frame = summary["frame_level"]
    temporal = summary["temporal_summary"]
    dropout_row = next((row for row in sar_temporal_rows if row.get("sample_pool") == "detection_dropout_temporal_continuation"), {})
    sar_only_row = next((row for row in sar_temporal_rows if row.get("sample_pool") == "sar_only_gt_reference"), {})
    return [
        {
            "probe_id": "J1",
            "factor_combination": "F_az + F_shell + F_sar_image",
            "sample_pool": "paired_optical_object_sar_gt",
            "n_samples": str(frame.get("n_frames", "")),
            "provenance_labels": "runtime_safe_geometry_or_vehicle_physics;SAR_image_observation;SAR_GT_posthoc_evidence;hypothesis_to_validate",
            "evidence_summary": f"azimuth original pass={frame.get('azimuth_original_pass_rate')}; tight shell pass={frame.get('tight_shell_pass_rate')}; paired peak/background median={fmt(correspondence_summary.get('scatter_peak_to_background_median'), 4)}",
            "joint_result": "Physical shell plus azimuth is promising only when SAR local scatter is treated as SAR observation, not as optical prior.",
            "limits": "GM_RM019 azimuth is weak; shell hit alone is not localization; GT crop scatter is posthoc.",
            "next_action": "Measure SAR peaks inside runtime-safe azimuth-shell regions without GT crop centers.",
            "guardrail_note": "No selector, ranking, or annotation proposal generated.",
        },
        {
            "probe_id": "J2",
            "factor_combination": "F_range_shape + F_traj",
            "sample_pool": "paired object hypotheses",
            "n_samples": str(summary["object_level"]["n_objects"]),
            "provenance_labels": "runtime_safe_optical_evidence;runtime_safe_temporal_evidence;SAR_GT_posthoc_evidence;hypothesis_to_validate",
            "evidence_summary": f"frame correlations area/height/bottom_y={frame.get('area_radius_pearson')}/{frame.get('height_radius_pearson')}/{frame.get('bottom_y_radius_pearson')}; object area trend={json.dumps(temporal.get('area_vs_radius_trend_counts', {}), ensure_ascii=False)}",
            "joint_result": "Shape/range is stronger when interpreted through object trend and state, not as single-frame correlation.",
            "limits": "Only one clean temporal object; GM_RM017/repeated frames dominate.",
            "next_action": "Separate complete morphology frames and review GM_RM019 continuity.",
            "guardrail_note": "Frame-level correlation is not promoted to runtime law.",
        },
        {
            "probe_id": "J3",
            "factor_combination": "F_traj + SAR_GT_center + SAR local peak drift",
            "sample_pool": "paired object hypotheses",
            "n_samples": str(len([row for row in sar_temporal_rows if row.get("sample_pool") == "paired_optical_object_sar_gt"])),
            "provenance_labels": "runtime_safe_temporal_evidence;SAR_temporal_observation;SAR_image_observation;SAR_GT_posthoc_evidence;hypothesis_to_validate",
            "evidence_summary": "SAR local peak/centroid drift was computed inside GT crops for object-level rows.",
            "joint_result": "This is a useful posthoc diagnostic for whether SAR scattering moves coherently with SAR GT centers.",
            "limits": "GT-crop peak drift cannot be a runtime prior; sparse objects remain insufficient.",
            "next_action": "Recompute peak drift in optical-derived SAR support regions.",
            "guardrail_note": "No identity truth claim.",
        },
        {
            "probe_id": "J4",
            "factor_combination": "dropout/severe truncation + optical temporal continuation + SAR temporal support",
            "sample_pool": "detection dropout / no_oty_iou_match / temporal continuation pool",
            "n_samples": str(dropout_row.get("n_samples", "")),
            "provenance_labels": str(dropout_row.get("provenance_labels", "")),
            "evidence_summary": str(dropout_row.get("temporal_support_summary", "")),
            "joint_result": "Dropout rows support target existence recovery, not clean paired morphology.",
            "limits": "All rows require manual review and remain excluded from clean shape statistics.",
            "next_action": "Use only as special mechanism pool and possible detector A/B review set.",
            "guardrail_note": "Propagation boxes are diagnostic only.",
        },
        {
            "probe_id": "J5",
            "factor_combination": "SAR-only 20 + paired SAR morphology",
            "sample_pool": "sar_only_gt_reference",
            "n_samples": str(sar_only_row.get("n_samples", "")),
            "provenance_labels": str(sar_only_row.get("provenance_labels", "")),
            "evidence_summary": f"SAR-only peak/background median={sar_only_row.get('peak_to_background_median')}; paired peak/background median={fmt(correspondence_summary.get('scatter_peak_to_background_median'), 4)}",
            "joint_result": "SAR-only rows are useful SAR morphology references and must not enter optical-SAR correspondence statistics.",
            "limits": "No optical object stream counterpart.",
            "next_action": "Use for SAR observation templates only.",
            "guardrail_note": "SAR-only pool remains separate.",
        },
        {
            "probe_id": "J6",
            "factor_combination": "GM_RM019 complex trajectory + manual optical GT / identity review",
            "sample_pool": "GM_RM019 paired and dropout pools",
            "n_samples": str(summary["scene_counts_paired"].get("GM_RM019", "")),
            "provenance_labels": "manual_or_review_anchor;runtime_safe_optical_evidence;SAR_GT_posthoc_evidence;hypothesis_to_validate",
            "evidence_summary": "GM_RM019 has 16 paired frames, 5 object hypotheses, weak azimuth coverage, sparse object trends, and 6 dropout/no-match rows.",
            "joint_result": "A small optical-side GT/identity review can clarify object hypotheses and complete morphology frames.",
            "limits": "Review may confirm object continuity, not SAR identity truth.",
            "next_action": "Prioritize GM_RM019 object continuity and complete-frame review before generalizing.",
            "guardrail_note": "No identity truth declared.",
        },
        {
            "probe_id": "J7",
            "factor_combination": "GM_RM011 blocked pool + object stream recovery",
            "sample_pool": "blocked_missing_gm011_object_stream",
            "n_samples": str(summary["sample_ledger"]["category_counts"].get("blocked_missing_gm011_object_stream", "")),
            "provenance_labels": "runtime_safe_optical_evidence;manual_or_review_anchor;hypothesis_to_validate",
            "evidence_summary": "GM_RM011 has SAR GT/review optical linkage but no current OTY optical object stream for 195 rows.",
            "joint_result": "The blocker is missing current object flow, not missing annotation.",
            "limits": "Cannot enter object-level optical-SAR correspondence until OTY object stream is built.",
            "next_action": "Run GM_RM011 through OTY0/OTY1/OTY1t object stream construction without SAR GT/image inputs.",
            "guardrail_note": "GM_RM011 not mixed into clean paired statistics.",
        },
    ]


def build_manual_review_rows(
    object_ledger: Sequence[Mapping[str, Any]],
    dropout_temporal_rows: Sequence[Mapping[str, str]],
    summary: Mapping[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in object_ledger:
        scene = str(row.get("scene", ""))
        need = str(row.get("review_need", ""))
        if scene == "GM_RM019" or "review-only" in need or "state-mixed" in need:
            priority = "high" if scene == "GM_RM019" and ("sparse" in need or "low azimuth" in need) else "medium"
            rows.append(
                {
                    "priority": priority,
                    "scene": scene,
                    "object_hypothesis_id": row.get("object_hypothesis_id", ""),
                    "sample_pool": "paired_optical_object_sar_gt",
                    "optical_frame_span": row.get("optical_frame_span", ""),
                    "sar_frame_span": row.get("sar_frame_span", ""),
                    "n_samples": row.get("n_paired_frames", ""),
                    "review_need": "optical_gt_or_identity_continuity_review",
                    "reason": need,
                    "mechanism_relevance": "Confirms object hypothesis continuity, trajectory direction, and complete morphology frames.",
                    "required_inputs": "Optical frames, current OTY object stream rows, review optical boxes; no SAR GT/image input for stream construction.",
                    "not_identity_truth_note": "Review can anchor optical object hypotheses but this report does not declare identity truth.",
                    "provenance_labels": "manual_or_review_anchor;runtime_safe_optical_evidence;hypothesis_to_validate",
                }
            )
    for row in dropout_temporal_rows:
        priority = "high" if row.get("scene") == "GM_RM019" else "medium"
        rows.append(
            {
                "priority": priority,
                "scene": row.get("scene", ""),
                "object_hypothesis_id": row.get("same_track_ids", ""),
                "sample_pool": "detection_dropout_temporal_continuation",
                "optical_frame_span": row.get("optical_frame", ""),
                "sar_frame_span": row.get("sar_frame", ""),
                "n_samples": "1",
                "review_need": "dropout_or_severe_truncation_temporal_continuation_review",
                "reason": f"sar_gt_id={row.get('sar_gt_id', '')}; current primary missing; manual_review_required={row.get('manual_review_required', '')}",
                "mechanism_relevance": "Tests whether optical temporal continuation and SAR support recover target existence in dropout/truncation states.",
                "required_inputs": "Current frame and +/- temporal optical frames, OTY object stream, review bbox context.",
                "not_identity_truth_note": "This is existence/continuation review, not final SAR label or identity truth.",
                "provenance_labels": "manual_or_review_anchor;runtime_safe_temporal_evidence;SAR_temporal_observation;hypothesis_to_validate",
            }
        )
    rows.append(
        {
            "priority": "high",
            "scene": "GM_RM011",
            "object_hypothesis_id": "",
            "sample_pool": "blocked_missing_gm011_object_stream",
            "optical_frame_span": "scene-level",
            "sar_frame_span": "scene-level",
            "n_samples": str(summary["sample_ledger"]["category_counts"].get("blocked_missing_gm011_object_stream", "")),
            "review_need": "object_stream_recovery_input_need",
            "reason": "GM_RM011 has SAR GT/review optical linkage but no current OTY optical object stream.",
            "mechanism_relevance": "Required before GM_RM011 can enter optical-object to SAR-GT mechanism modeling.",
            "required_inputs": "Run GM_RM011 through OTY0/OTY1/OTY1t object-stream construction using optical data only.",
            "not_identity_truth_note": "Recovery establishes an optical object stream candidate, not SAR identity truth.",
            "provenance_labels": "runtime_safe_optical_evidence;manual_or_review_anchor;hypothesis_to_validate",
        }
    )
    priority_order = {"high": 0, "medium": 1, "low": 2}
    return sorted(rows, key=lambda item: (priority_order.get(str(item.get("priority")), 9), str(item.get("scene", "")), str(item.get("optical_frame_span", ""))))


def question_answers(summary: Mapping[str, Any], correspondence_summary: Mapping[str, Any]) -> dict[str, str]:
    return {
        "1_strong_posthoc_support": (
            "F_time, broad F_az, F_shell compression, F_range_shape for height/bottom_y/area, and F_sar_image local peak evidence. "
            f"Paired peak/background median={fmt(correspondence_summary.get('scatter_peak_to_background_median'), 4)}; temporal window pass={summary['frame_level'].get('temporal_window_pass_rate')}."
        ),
        "2_state_conditioned": (
            "F_az and F_range_shape are state/scene conditioned; GM_RM019, edge, duplicate/handoff, review-only, and dropout rows need wider uncertainty or separate routing."
        ),
        "3_physical_but_insufficient": (
            "Mainlobe/sidelobe, IRW/PSLR/ISLR/ENL-like metrics, SAR scattering centroid drift, and scene-level bias have SAR imaging explanations but need non-GT region extraction and more balanced objects."
        ),
        "4_joint_validation": (
            "Use F_az+F_shell+F_sar_image, F_range_shape+F_traj, F_traj+SAR temporal peak drift, and dropout+optical continuation+SAR support as joint probes."
        ),
        "5_dominated_or_sparse": (
            "Results are dominated by GM_RM017 and repeated frame-level rows: 199/215 paired frames are GM_RM017, while object hypotheses total only 9."
        ),
        "6_gmrm019_review": (
            "GM_RM019 needs optical-side continuity/identity review for sparse objects, weak azimuth coverage, partial/edge/duplicate states, and six dropout/no-match cases."
        ),
        "7_gmrm011_recovery": (
            "GM_RM011 needs OTY optical object stream recovery for 195 blocked rows; it is not unannotated and cannot be mixed into clean paired correspondence yet."
        ),
        "8_future_runtime_safe": (
            "F_time, F_az, F_shell, F_state, and optical trajectory features can become runtime-safe candidates; F_range_shape needs an independent runtime-safe range hypothesis first."
        ),
        "9_posthoc_only": (
            "SAR GT coverage, GT-crop SAR image statistics, manual review anchors, SAR-only morphology, dropout SAR support, and shape-radius correlations remain posthoc observations."
        ),
        "10_matlab_reference": (
            "The MATLAB toolbox inspires range-azimuth grids, focusing, local peak, mainlobe/sidelobe, IRW/PSLR/ISLR/ENL, and motion-compensation vocabulary, but it is similar_imaging_reference_only because its raw data, parameters, axes, frame rate, and preprocessing are not the current OTY2 pipeline."
        ),
    }


def render_plan_doc(path: Path, timestamp: str, outputs: Mapping[str, str]) -> None:
    lines = [
        "# OTY2 Object-SAR Physical Mechanism Modeling Plan",
        "",
        f"Updated: {timestamp}",
        "",
        "This plan records the next modeling step after OTY2 posthoc validation. It is not OTY3, not an automatic annotation proposal, not a selector/ranking design, and not training or threshold tuning.",
        "",
        "## Objective",
        "",
        "Model how an optical object hypothesis maps to SAR GT / SAR image evidence through physical factors: time synchronization, fan-polar azimuth, vehicle shell, optical range-shape cues, optical trajectory, SAR image scattering, SAR temporal continuity, and state-conditioned uncertainty.",
        "",
        "## Evidence Boundaries",
        "",
        "- Runtime-safe construction may use optical object stream, optical temporal continuity, acquisition timing, scene geometry, and vehicle physical assumptions.",
        "- SAR GT, SAR image crop statistics, and manual/review anchors may be used only as posthoc validation or SAR observation evidence.",
        "- SAR image evidence is important for final annotation reasoning, but posthoc SAR GT / SAR image discoveries must not be written back into runtime optical prior construction.",
        "- The uploaded MATLAB imaging toolbox is similar_imaging_reference_only: it explains SAR/FMCW concepts such as range FFT, range-azimuth grids, BP focusing, mainlobe/sidelobe, IRW/PSLR/ISLR/ENL, and motion compensation; it is not the same OTY2 pipeline and the zip is not committed.",
        "",
        "## Ledger Pools",
        "",
        "- paired_optical_object_sar_gt = 215",
        "- blocked_missing_gm011_object_stream = 195",
        "- sar_only_gt = 20",
        "- detection dropout / no_oty_iou_match / temporal continuation pool = 12",
        "",
        "The 215 paired rows are frame-level posthoc pairs, not 215 independent physical objects. SAR-only rows stay outside optical-SAR correspondence statistics. Dropout/no-match rows stay outside clean paired morphology statistics.",
        "",
        "## Factor Families",
        "",
        "- F_time: 24fps optical to 50fps SAR software-sync temporal tube.",
        "- F_az: fan-polar / range-azimuth azimuth mapping.",
        "- F_shell: vehicle physical length/width footprint shell.",
        "- F_range_shape: complete-state optical bbox height / bottom_y / area relation to SAR radius.",
        "- F_traj: optical object trajectory direction and SAR GT trend.",
        "- F_sar_image: SAR local peak, mainlobe/sidelobe, long/short axis, box/background, peak/background.",
        "- F_sar_temporal: SAR scattering continuity across adjacent SAR frames.",
        "- F_state: complete / truncated / edge / far-small / duplicate / dropout conditioned uncertainty.",
        "",
        "## Immediate Modeling Use",
        "",
        "1. Use F_az + F_shell + F_sar_image as a joint SAR observation probe, not a candidate selector.",
        "2. Use F_range_shape + F_traj only as object-level posthoc hypotheses until complete-state and scene balance improve.",
        "3. Use F_sar_temporal for SAR observation inside the temporal tube, especially dropout/truncation cases.",
        "4. Use GM_RM019 manual optical GT / identity review to confirm object hypotheses, trajectory direction, and complete morphology frames, not SAR identity truth.",
        "5. Recover GM_RM011 through OTY optical object stream construction before optical-SAR correspondence modeling.",
        "",
        "## Prohibited Shortcuts",
        "",
        "- Do not treat 215 as 442.",
        "- Do not treat frame-level correlation as object-level law.",
        "- Do not mix SAR-only rows into optical-SAR correspondence.",
        "- Do not mix dropout/no-match rows into clean paired morphology.",
        "- Do not write SAR GT / SAR image posthoc discoveries into runtime prior construction.",
        "- Do not generate annotation proposals, selector/ranking outputs, tuned thresholds, model weights, or identity truth claims.",
        "",
        "## Generated Evidence Outputs",
        "",
    ]
    for name, output_path in outputs.items():
        lines.append(f"- {name}: `{output_path}`")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def render_report(
    path: Path,
    timestamp: str,
    summary: Mapping[str, Any],
    correspondence_summary: Mapping[str, Any],
    outputs: Mapping[str, str],
    sources: Mapping[str, str],
    answers: Mapping[str, str],
) -> None:
    ledger = summary["sample_ledger"]["category_counts"]
    frame = summary["frame_level"]
    temporal = summary["temporal_summary"]
    sar_only = summary["sar_only_summary"]
    lines = [
        "# OTY2 Physical Factor Modeling Report",
        "",
        f"生成时间：`{timestamp}`",
        "",
        "本报告是 OTY2 physical factor evidence ledger / mechanism modeling report。它使用 SAR GT、SAR 图像和人工/review 信息只做 posthoc validation 与 SAR observation 分层记录；不生成最终自动标注，不做 selector/ranking，不训练或调阈值，不声明 identity truth。",
        "",
        "## 样本总账",
        "",
        f"- 442 ledger：`{json.dumps(ledger, ensure_ascii=False)}`。",
        f"- paired frame-level rows：`{frame.get('n_frames')}`；object hypotheses：`{frame.get('n_objects')}`。",
        f"- 场景 paired：`{json.dumps(summary.get('scene_counts_paired', {}), ensure_ascii=False)}`。",
        f"- 状态分布：`{frame.get('status_counts')}`。",
        "- GM_RM011 的 195 条是 blocked_missing_object_stream，不是未标注；SAR-only 20 条只作 SAR morphology reference；dropout/no-match 12 条只作特殊机制池。",
        "",
        "## 核心量化结果",
        "",
        f"- F_time：temporal window pass rate `{frame.get('temporal_window_pass_rate')}`，使用 24fps -> 50fps 软件同步 temporal tube。",
        f"- F_az：original interval pass `{summary['azimuth_key_results']['original_interval']['coverage_rate']}`；40deg fixed margin pass `{summary['azimuth_key_results']['smallest_fixed_margin_ge_95_pass']['coverage_rate']}`；GM_RM019 是弱场景。",
        f"- F_shell：tight/base/relaxed pass `{summary['vehicle_shell_key_results']['tight_vehicle_shell']['coverage_rate']}` / `{summary['vehicle_shell_key_results']['base_vehicle_shell']['coverage_rate']}` / `{summary['vehicle_shell_key_results']['relaxed_vehicle_shell']['coverage_rate']}`；tight miss 仍有信息量。",
        f"- F_range_shape：area/height/bottom_y/aspect vs SAR radius Pearson `{frame.get('area_radius_pearson')}` / `{frame.get('height_radius_pearson')}` / `{frame.get('bottom_y_radius_pearson')}` / `{frame.get('aspect_radius_pearson')}`。",
        f"- F_traj：object-level trajectory reliability `{json.dumps(temporal.get('trajectory_reliability_counts', {}), ensure_ascii=False)}`；area-vs-radius object trend `{json.dumps(temporal.get('area_vs_radius_trend_counts', {}), ensure_ascii=False)}`。",
        f"- F_sar_image：paired peak/background median `{fmt(correspondence_summary.get('scatter_peak_to_background_median'), 4)}`；paired box/background median `{fmt(correspondence_summary.get('scatter_box_to_background_median'), 4)}`；SAR-only local peak supported `{sar_only.get('scatter_support_counts', {}).get('local_scatter_peak_supported', 0)}/{sar_only.get('sample_count')}`。",
        "",
        "## 十个问题回答",
        "",
    ]
    for index, key in enumerate(answers, start=1):
        lines.append(f"{index}. {answers[key]}")
    lines.extend(
        [
            "",
            "## 边界与下一步",
            "",
            "- 可以进入未来 runtime-safe factor 的方向：F_time、F_az、F_shell、F_state、光学对象轨迹；F_range_shape 需要独立 runtime-safe range hypothesis 后再验证。",
            "- 仍只能作为 posthoc observation 的内容：SAR GT 覆盖率、GT crop SAR 图像统计、SAR-only morphology、dropout SAR support、manual/review anchors、shape-radius 后验相关。",
            "- GM_RM019：补少量手动光学 GT / identity-continuity review，用于确认 object hypothesis、轨迹方向和完整形态帧；不声明身份真值。",
            "- GM_RM011：补 OTY optical object stream；不能把 195 blocked rows 混入 clean paired mechanism statistics。",
            "- MATLAB imaging code：只作为 similar_imaging_reference_only；不要提交 zip，不假设同 pipeline。",
            "",
            "## 输出文件",
            "",
        ]
    )
    for name, output_path in outputs.items():
        lines.append(f"- {name}: `{output_path}`")
    lines.extend(["", "## 数据源", ""])
    for name, source_path in sources.items():
        lines.append(f"- {name}: `{source_path}`")
    lines.extend(["", "## Boundary Flags", ""])
    for key, value in BOUNDARY_FLAGS.items():
        lines.append(f"- {key}: `{str(value).lower()}`")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_workspace_log(timestamp: str, outputs: Mapping[str, str], summary: Mapping[str, Any]) -> Path:
    WORKSPACE_LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = WORKSPACE_LOG_DIR / f"oty2_physical_factor_evidence_ledger_{timestamp}.log"
    lines = [
        f"timestamp={timestamp}",
        "task=oty2_physical_factor_evidence_ledger",
        "interpreter=D:\\MINICONDA\\envs\\py311\\python.exe",
        f"outputs={json.dumps(outputs, ensure_ascii=False)}",
        f"summary={json.dumps(summary, ensure_ascii=False)}",
    ]
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return log_path


def run(args: argparse.Namespace) -> dict[str, Any]:
    timestamp = args.timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    inputs = load_inputs(args)
    stratified_summary = inputs["stratified_summary"]
    correspondence_summary = inputs["correspondence_summary"]
    ledger = validate_ledger(stratified_summary)

    paired_scatter_records = build_paired_scatter_records(inputs["correspondence_rows"])
    scatter_by_object = object_scatter_summary(paired_scatter_records)
    sar_temporal_rows = build_sar_temporal_probe(
        scatter_by_object,
        inputs["dropout_temporal_rows"],
        inputs["dropout_sar_rows"],
        inputs["sar_only_rows"],
    )
    object_ledger = build_object_ledger(inputs["temporal_rows"], inputs["correspondence_rows"], scatter_by_object)
    taxonomy_rows = build_taxonomy(stratified_summary, correspondence_summary, sar_temporal_rows)
    joint_probe_rows = build_joint_probe_rows(stratified_summary, correspondence_summary, sar_temporal_rows)
    manual_review_rows = build_manual_review_rows(object_ledger, inputs["dropout_temporal_rows"], stratified_summary)
    answers = question_answers(stratified_summary, correspondence_summary)

    taxonomy_csv = REPORT_DIR / f"oty2_physical_factor_evidence_taxonomy_{timestamp}.csv"
    joint_csv = REPORT_DIR / f"oty2_joint_factor_probe_{timestamp}.csv"
    object_csv = REPORT_DIR / f"oty2_object_level_factor_evidence_ledger_{timestamp}.csv"
    sar_temporal_csv = REPORT_DIR / f"oty2_sar_temporal_observation_probe_{timestamp}.csv"
    manual_csv = REPORT_DIR / f"oty2_manual_review_candidate_list_{timestamp}.csv"
    report_md = REPORT_DIR / f"oty2_physical_factor_modeling_report_{timestamp}.md"
    summary_json = REPORT_DIR / f"oty2_physical_factor_modeling_summary_{timestamp}.json"
    plan_doc = DOCS_DIR / "oty2_object_sar_physical_mechanism_modeling_plan.md"

    outputs = {
        "plan_doc": str(plan_doc),
        "physical_factor_evidence_taxonomy_csv": str(taxonomy_csv),
        "joint_factor_probe_csv": str(joint_csv),
        "object_level_factor_evidence_ledger_csv": str(object_csv),
        "sar_temporal_observation_probe_csv": str(sar_temporal_csv),
        "manual_review_candidate_list_csv": str(manual_csv),
        "physical_factor_modeling_report_md": str(report_md),
        "physical_factor_modeling_summary_json": str(summary_json),
    }
    sources = {name: str(path) for name, path in inputs["paths"].items()}

    write_csv(taxonomy_csv, taxonomy_rows, TAXONOMY_FIELDS)
    write_csv(joint_csv, joint_probe_rows, JOINT_PROBE_FIELDS)
    write_csv(object_csv, object_ledger, OBJECT_LEDGER_FIELDS)
    write_csv(sar_temporal_csv, sar_temporal_rows, SAR_TEMPORAL_FIELDS)
    write_csv(manual_csv, manual_review_rows, MANUAL_REVIEW_FIELDS)
    render_plan_doc(plan_doc, timestamp, outputs)

    summary = {
        "timestamp": timestamp,
        "sample_ledger": ledger,
        "source_timestamps": {
            "stratified_validation": stratified_summary.get("timestamp"),
            "gt_correspondence_mechanism": correspondence_summary.get("timestamp"),
        },
        "row_counts": {
            "factor_taxonomy": len(taxonomy_rows),
            "joint_factor_probe": len(joint_probe_rows),
            "object_level_factor_evidence_ledger": len(object_ledger),
            "sar_temporal_observation_probe": len(sar_temporal_rows),
            "manual_review_candidate_list": len(manual_review_rows),
            "paired_scatter_records_recomputed": len(paired_scatter_records),
        },
        "key_metrics": {
            "paired_peak_to_background_median": fmt(correspondence_summary.get("scatter_peak_to_background_median"), 4),
            "paired_box_to_background_median": fmt(correspondence_summary.get("scatter_box_to_background_median"), 4),
            "azimuth_original_coverage": stratified_summary["azimuth_key_results"]["original_interval"]["coverage_rate"],
            "tight_shell_coverage": stratified_summary["vehicle_shell_key_results"]["tight_vehicle_shell"]["coverage_rate"],
            "base_shell_coverage": stratified_summary["vehicle_shell_key_results"]["base_vehicle_shell"]["coverage_rate"],
            "range_shape_height_radius_pearson": stratified_summary["frame_level"]["height_radius_pearson"],
            "object_trajectory_reliability_counts": stratified_summary["temporal_summary"]["trajectory_reliability_counts"],
        },
        "question_answers": answers,
        "boundary_flags": BOUNDARY_FLAGS,
        "outputs": outputs,
        "sources": sources,
    }
    write_json(summary_json, summary)
    render_report(report_md, timestamp, stratified_summary, correspondence_summary, outputs, sources, answers)
    log_path = write_workspace_log(timestamp, outputs, summary)
    summary["outputs"]["workspace_log"] = str(log_path)
    write_json(summary_json, summary)
    print(json.dumps({"outputs": summary["outputs"], "row_counts": summary["row_counts"], "boundary_flags": BOUNDARY_FLAGS}, ensure_ascii=False, indent=2))
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timestamp", default="")
    parser.add_argument("--stratified-summary-json", default="")
    parser.add_argument("--stratified-csv", default="")
    parser.add_argument("--azimuth-csv", default="")
    parser.add_argument("--shell-csv", default="")
    parser.add_argument("--shape-csv", default="")
    parser.add_argument("--temporal-csv", default="")
    parser.add_argument("--sar-only-csv", default="")
    parser.add_argument("--correspondence-csv", default="")
    parser.add_argument("--correspondence-summary-json", default="")
    parser.add_argument("--dropout-temporal-csv", default="")
    parser.add_argument("--dropout-sar-csv", default="")
    parser.add_argument("--accounting-csv", default="")
    return parser


def main() -> None:
    run(build_parser().parse_args())


if __name__ == "__main__":
    main()
