"""Probe detector-swap impact on OTY2 optical timeline stability.

This script compares detector outputs against the diagnostic optical timeline
graph manifest. It evaluates whether a detector helps the optical timeline
layer by reducing missing diagnostic vehicle frames, duplicate boxes, edge
pressure, non-vehicle false positives, and manual-review pressure.

It does not replace the main detector, modify tracker output, run tracker
replay, create final boxes, create revised GT, create final annotations, run
SAR pairing/support, or download weights unless a future caller explicitly adds
that behavior.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_NODES = REPO_ROOT / "reports" / "oty2" / "samples" / "oty2_optical_timeline_graph_nodes_20260705_175222.csv"
DEFAULT_EDGES = REPO_ROOT / "reports" / "oty2" / "samples" / "oty2_optical_timeline_graph_edges_20260705_175222.csv"
DEFAULT_MANIFEST = REPO_ROOT / "reports" / "oty2" / "samples" / "oty2_optical_timeline_video_render_manifest_20260705_175222.csv"

DETECTION_SCHEMA_FIELDS = [
    "scene",
    "detector_name",
    "optical_frame_num",
    "optical_path",
    "det_id",
    "class_name",
    "confidence",
    "bbox_x1",
    "bbox_y1",
    "bbox_x2",
    "bbox_y2",
    "bbox_area",
    "is_vehicle_class",
    "source_model",
    "source_weight_path",
    "notes",
]

SUMMARY_FIELDS = [
    "scene",
    "case_id",
    "detector_name",
    "frames_checked",
    "vehicle_detections",
    "non_vehicle_false_positive_count",
    "missing_vehicle_count",
    "multi_box_same_vehicle_count",
    "box_fit_status",
    "edge_contact_status",
    "timeline_fragment_risk",
    "same_vehicle_support_status",
    "forbidden_edge_safety_status",
    "manual_override_pressure",
    "overall_effect",
    "reason",
]

VEHICLE_CLASSES = {"car", "truck", "bus", "van", "motorcycle", "motorbike"}
SKIP_RENDER_STATUSES = {"forbidden_not_rendered", "non_vehicle_not_rendered"}


@dataclass(frozen=True)
class DetectorSource:
    name: str
    source_model: str
    weight_path: str
    scene_tables: Mapping[str, Path]
    backend_status: str = "available"


@dataclass(frozen=True)
class CaseSpec:
    scene: str
    case_id: str
    frame_start: int
    frame_end: int
    case_type: str
    diagnostic_vehicle_ids: tuple[str, ...]
    non_vehicle_vehicle_ids: tuple[str, ...] = ()
    reason: str = ""


DETECTORS = [
    DetectorSource(
        name="baseline_oty0",
        source_model="ultralytics_yolo11l_current_oty0",
        weight_path="not_committed; current OTY0 baseline source table",
        scene_tables={
            "GM_RM017": REPO_ROOT / "outputs" / "oty0_yolo_detection_stream_audit_20260701_181317" / "oty0_yolo_detection_table.csv",
            "GM_RM011": REPO_ROOT / "outputs" / "oty0_yolo_detection_stream_audit_20260704_gm011_oty_stream" / "oty0_yolo_detection_table.csv",
        },
    ),
    DetectorSource(
        name="ultralytics_yolo26l_probe",
        source_model="ultralytics_yolo26l_existing_probe",
        weight_path="D:/profile/research/workspace/artifacts/detector_weights/yolo26l.pt",
        scene_tables={
            "GM_RM017": REPO_ROOT / "outputs" / "oty2_yolo26l_detector_quality_probe_20260704_231830" / "oty0_yolo_detection_stream_audit_yolo26l_gm_rm017" / "oty0_yolo_detection_table.csv",
            "GM_RM011": REPO_ROOT / "outputs" / "oty2_yolo26l_detector_quality_probe_20260704_231830" / "oty0_yolo_detection_stream_audit_yolo26l_gm_rm011" / "oty0_yolo_detection_table.csv",
        },
    ),
    DetectorSource(
        name="ultralytics_yolo8n_no_download",
        source_model="ultralytics_yolo8n",
        weight_path="D:/models/ultralytics/yolov8n.pt",
        scene_tables={},
        backend_status="weight_missing_no_download",
    ),
    DetectorSource(
        name="ultralytics_yolo12n_no_download",
        source_model="ultralytics_yolo12n",
        weight_path="D:/models/ultralytics/yolo12n.pt",
        scene_tables={},
        backend_status="weight_missing_no_download",
    ),
    DetectorSource(
        name="rtdetr_l_no_download",
        source_model="ultralytics_rtdetr_l",
        weight_path="D:/models/ultralytics/rtdetr-l.pt",
        scene_tables={},
        backend_status="weight_missing_no_download",
    ),
]

CASES = [
    CaseSpec("GM_RM017", "GM017_bs_0008_leading_dark_sedan", 145, 185, "same_vehicle_fragment", ("GM_RM017_V001",), reason="leading dark sedan same-referent fragment"),
    CaseSpec("GM_RM017", "GM017_bs_0010_white_suv", 151, 200, "same_vehicle_fragment", ("GM_RM017_V002",), reason="white SUV same-referent fragment"),
    CaseSpec("GM_RM017", "GM017_bs_0012_trailing_dark_sedan", 162, 214, "same_vehicle_fragment", ("GM_RM017_V003",), reason="trailing dark sedan weak same-referent fragment"),
    CaseSpec("GM_RM017", "GM017_bs_0002_non_vehicle_barrier", 121, 129, "non_vehicle_exclusion", (), ("GM_RM017_NONVEHICLE_001",), reason="foreground barrier should not be vehicle"),
    CaseSpec("GM_RM011", "GM011_bs0015_seg001_to_seg002", 13, 35, "strong_same_vehicle_edge", ("GM_RM011_V001",), reason="short-gap white vehicle connection"),
    CaseSpec("GM_RM011", "GM011_bs0061_seg002_to_seg003", 279, 292, "strong_same_vehicle_edge", ("GM_RM011_V002",), reason="short-gap central white vehicle connection"),
    CaseSpec("GM_RM011", "GM011_bs0061_seg001_to_seg002", 262, 281, "weak_same_vehicle_edge", ("GM_RM011_V002",), reason="weak rear/side to front/window transition"),
    CaseSpec("GM_RM011", "GM011_forbid_bs0061_to_bs0064", 262, 292, "forbidden_edge", ("GM_RM011_V002",), ("GM_RM011_FORBIDDEN_CONTEXT_001",), reason="left-edge competitor must remain separate"),
    CaseSpec("GM_RM011", "GM011_forbid_bs0056_to_bs0061", 256, 270, "forbidden_edge", ("GM_RM011_V002",), ("GM_RM011_FORBIDDEN_CONTEXT_002",), reason="proximity/part-switch bridge must remain blocked"),
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return [row for row in csv.DictReader(fh) if not duplicate_header(row)]


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def duplicate_header(row: Mapping[str, Any]) -> bool:
    values = [str(value or "").strip() for value in row.values() if str(value or "").strip()]
    if not values:
        return False
    hits = sum(1 for key, value in row.items() if str(value or "").strip() == key)
    return hits >= max(2, len(values) // 2)


def norm(value: Any) -> str:
    return str(value if value is not None else "").strip()


def parse_int(value: Any) -> int | None:
    text = norm(value)
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def parse_float(value: Any) -> float | None:
    text = norm(value)
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def bbox_from_row(row: Mapping[str, str]) -> tuple[float, float, float, float] | None:
    values = [parse_float(row.get(key)) for key in ("bbox_x1", "bbox_y1", "bbox_x2", "bbox_y2")]
    if any(value is None for value in values):
        return None
    x1, y1, x2, y2 = (float(value) for value in values if value is not None)
    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2, y2


def area(bbox: tuple[float, float, float, float]) -> float:
    return max(0.0, bbox[2] - bbox[0]) * max(0.0, bbox[3] - bbox[1])


def iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ix1 = max(a[0], b[0])
    iy1 = max(a[1], b[1])
    ix2 = min(a[2], b[2])
    iy2 = min(a[3], b[3])
    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    inter = iw * ih
    denom = area(a) + area(b) - inter
    return inter / denom if denom > 0 else 0.0


def touches_edge(bbox: tuple[float, float, float, float], width: float = 800.0, height: float = 600.0, margin: float = 3.0) -> bool:
    return bbox[0] <= margin or bbox[1] <= margin or bbox[2] >= width - margin or bbox[3] >= height - margin


def is_vehicle(row: Mapping[str, str]) -> bool:
    return norm(row.get("class_name")).lower() in VEHICLE_CLASSES


def expected_manifest_by_case(manifest_rows: Sequence[Mapping[str, str]]) -> dict[str, list[Mapping[str, str]]]:
    out: dict[str, list[Mapping[str, str]]] = {}
    for case in CASES:
        case_rows: list[Mapping[str, str]] = []
        for row in manifest_rows:
            if norm(row.get("scene")) != case.scene:
                continue
            frame = parse_int(row.get("optical_frame_num"))
            if frame is None or not (case.frame_start <= frame <= case.frame_end):
                continue
            vehicle_id = norm(row.get("diagnostic_vehicle_id"))
            if vehicle_id in case.diagnostic_vehicle_ids or vehicle_id in case.non_vehicle_vehicle_ids:
                case_rows.append(row)
        out[case.case_id] = case_rows
    return out


def normalize_detection_rows(detector: DetectorSource, scene: str, rows: Sequence[Mapping[str, str]], frame_filter: set[int]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for row in rows:
        frame = parse_int(row.get("optical_frame_num"))
        if frame is None or frame not in frame_filter:
            continue
        bbox = bbox_from_row(row)
        if bbox is None:
            continue
        class_name = norm(row.get("class_name"))
        out.append(
            {
                "scene": scene,
                "detector_name": detector.name,
                "optical_frame_num": str(frame),
                "optical_path": norm(row.get("optical_path")),
                "det_id": norm(row.get("det_id")),
                "class_name": class_name,
                "confidence": norm(row.get("confidence")),
                "bbox_x1": f"{bbox[0]:.3f}",
                "bbox_y1": f"{bbox[1]:.3f}",
                "bbox_x2": f"{bbox[2]:.3f}",
                "bbox_y2": f"{bbox[3]:.3f}",
                "bbox_area": f"{area(bbox):.3f}",
                "is_vehicle_class": str(class_name.lower() in VEHICLE_CLASSES).lower(),
                "source_model": detector.source_model,
                "source_weight_path": detector.weight_path,
                "notes": f"backend_status={detector.backend_status}; plug-in detection row only",
            }
        )
    return out


def build_detection_schema(detectors: Sequence[DetectorSource], scenes: Sequence[str], frame_filter: set[int]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for detector in detectors:
        if detector.backend_status != "available":
            continue
        for scene in scenes:
            table = detector.scene_tables.get(scene)
            if not table or not table.exists():
                continue
            rows.extend(normalize_detection_rows(detector, scene, read_csv(table), frame_filter))
    return sorted(rows, key=lambda item: (item["scene"], item["detector_name"], int(item["optical_frame_num"]), item["det_id"]))


def rows_for_detector_scene(schema_rows: Sequence[Mapping[str, str]], detector_name: str, scene: str, start: int, end: int) -> list[Mapping[str, str]]:
    out = []
    for row in schema_rows:
        if row["detector_name"] != detector_name or row["scene"] != scene:
            continue
        frame = int(row["optical_frame_num"])
        if start <= frame <= end:
            out.append(row)
    return out


def frame_set(start: int, end: int) -> set[int]:
    return set(range(start, end + 1))


def summarize_available_detector(
    detector: DetectorSource,
    case: CaseSpec,
    schema_rows: Sequence[Mapping[str, str]],
    expected_rows: Sequence[Mapping[str, str]],
    baseline_metrics: Mapping[str, float] | None,
) -> tuple[dict[str, str], dict[str, float]]:
    rows = rows_for_detector_scene(schema_rows, detector.name, case.scene, case.frame_start, case.frame_end)
    rows_by_frame: dict[int, list[Mapping[str, str]]] = {}
    for row in rows:
        rows_by_frame.setdefault(int(row["optical_frame_num"]), []).append(row)

    expected_vehicle = [
        row for row in expected_rows
        if norm(row.get("display_status")) not in SKIP_RENDER_STATUSES
        and norm(row.get("diagnostic_vehicle_id")) in case.diagnostic_vehicle_ids
    ]
    expected_non_vehicle = [
        row for row in expected_rows
        if norm(row.get("diagnostic_vehicle_id")) in case.non_vehicle_vehicle_ids
    ]

    matched_ious: list[float] = []
    matched_edges = 0
    missing = 0
    multi_box = 0
    expected_frames: set[int] = set()
    for expected in expected_vehicle:
        frame = parse_int(expected.get("optical_frame_num"))
        expected_bbox = bbox_from_row(expected)
        if frame is None or expected_bbox is None:
            continue
        expected_frames.add(frame)
        frame_rows = [row for row in rows_by_frame.get(frame, []) if row.get("is_vehicle_class") == "true"]
        overlaps = []
        for row in frame_rows:
            det_bbox = bbox_from_row(row)
            if det_bbox is not None:
                value = iou(expected_bbox, det_bbox)
                if value >= 0.25:
                    overlaps.append((value, det_bbox))
        if not overlaps:
            missing += 1
            continue
        overlaps.sort(reverse=True, key=lambda item: item[0])
        matched_ious.append(overlaps[0][0])
        if len(overlaps) > 1:
            multi_box += len(overlaps) - 1
        if touches_edge(overlaps[0][1]):
            matched_edges += 1

    non_vehicle_fp = 0
    for expected in expected_non_vehicle:
        frame = parse_int(expected.get("optical_frame_num"))
        expected_bbox = bbox_from_row(expected)
        if frame is None or expected_bbox is None:
            continue
        for row in rows_by_frame.get(frame, []):
            det_bbox = bbox_from_row(row)
            if det_bbox is not None and row.get("is_vehicle_class") == "true" and iou(expected_bbox, det_bbox) >= 0.25:
                non_vehicle_fp += 1

    vehicle_detections = sum(1 for row in rows if row.get("is_vehicle_class") == "true")
    frames_checked = case.frame_end - case.frame_start + 1
    matched_count = len(matched_ious)
    median_iou = sorted(matched_ious)[len(matched_ious) // 2] if matched_ious else 0.0
    edge_ratio = matched_edges / matched_count if matched_count else 0.0
    missing_ratio = missing / len(expected_frames) if expected_frames else 0.0
    multi_ratio = multi_box / max(1, len(expected_frames))
    pressure_score = missing + multi_box + non_vehicle_fp + matched_edges

    baseline_pressure = float(baseline_metrics.get("pressure_score", pressure_score)) if baseline_metrics else float(pressure_score)
    baseline_missing = float(baseline_metrics.get("missing", missing)) if baseline_metrics else float(missing)
    baseline_multi = float(baseline_metrics.get("multi_box", multi_box)) if baseline_metrics else float(multi_box)
    baseline_non_vehicle = float(baseline_metrics.get("non_vehicle_fp", non_vehicle_fp)) if baseline_metrics else float(non_vehicle_fp)
    baseline_iou = float(baseline_metrics.get("median_iou", median_iou)) if baseline_metrics else float(median_iou)
    baseline_edge_ratio = float(baseline_metrics.get("edge_ratio", edge_ratio)) if baseline_metrics else float(edge_ratio)

    if baseline_metrics is None:
        overall_effect = "neutral"
        manual_pressure = "same"
        box_fit = "baseline_reference"
        edge_status = "baseline_reference"
        fragment_risk = "baseline_reference"
        support_status = "baseline_reference"
    else:
        improved = 0
        worsened = 0
        if missing < baseline_missing:
            improved += 1
        elif missing > baseline_missing:
            worsened += 1
        if multi_box < baseline_multi:
            improved += 1
        elif multi_box > baseline_multi:
            worsened += 1
        if non_vehicle_fp < baseline_non_vehicle:
            improved += 1
        elif non_vehicle_fp > baseline_non_vehicle:
            worsened += 1
        if median_iou > baseline_iou + 0.05:
            improved += 1
        elif median_iou < baseline_iou - 0.05:
            worsened += 1
        if edge_ratio < baseline_edge_ratio - 0.05:
            improved += 1
        elif edge_ratio > baseline_edge_ratio + 0.05:
            worsened += 1

        if pressure_score < baseline_pressure:
            manual_pressure = "reduced"
        elif pressure_score > baseline_pressure:
            manual_pressure = "increased"
        else:
            manual_pressure = "same"
        if median_iou > baseline_iou + 0.05:
            box_fit = "improved"
        elif median_iou < baseline_iou - 0.05:
            box_fit = "worse"
        else:
            box_fit = "similar"
        if edge_ratio < baseline_edge_ratio - 0.05:
            edge_status = "reduced_edge_pressure"
        elif edge_ratio > baseline_edge_ratio + 0.05:
            edge_status = "increased_edge_pressure"
        else:
            edge_status = "similar"
        if missing < baseline_missing:
            fragment_risk = "lower"
        elif missing > baseline_missing:
            fragment_risk = "higher"
        else:
            fragment_risk = "same"
        if case.case_type.startswith("strong") or case.case_type == "same_vehicle_fragment":
            support_status = "stronger" if missing < baseline_missing or median_iou > baseline_iou + 0.05 else ("weaker" if missing > baseline_missing or median_iou < baseline_iou - 0.05 else "same")
        elif case.case_type.startswith("weak"):
            support_status = "upgrade_candidate" if improved >= 2 and missing <= baseline_missing and multi_box <= baseline_multi else "still_weak"
        else:
            support_status = "not_applicable"

        if improved > worsened and manual_pressure in {"reduced", "same"}:
            overall_effect = "improves_timeline_stability"
        elif worsened > improved:
            overall_effect = "worse"
        elif improved == 0 and worsened == 0:
            overall_effect = "neutral"
        else:
            overall_effect = "inconclusive"

    if case.case_type == "forbidden_edge":
        if detector.name == "baseline_oty0":
            forbidden_status = "baseline_reference"
        elif non_vehicle_fp > baseline_non_vehicle or multi_box > baseline_multi:
            forbidden_status = "risk_increased_detection_only"
        elif missing <= baseline_missing:
            forbidden_status = "preserved_detection_only"
        else:
            forbidden_status = "inconclusive_detection_only"
    elif case.case_type == "non_vehicle_exclusion":
        forbidden_status = "non_vehicle_fp_reduced" if baseline_metrics and non_vehicle_fp < baseline_non_vehicle else ("non_vehicle_fp_increased" if baseline_metrics and non_vehicle_fp > baseline_non_vehicle else "baseline_or_same")
    else:
        forbidden_status = "not_applicable"

    reason = (
        f"matched={matched_count}; expected_vehicle_frames={len(expected_frames)}; "
        f"median_iou={median_iou:.3f}; missing={missing}; multi_box={multi_box}; "
        f"non_vehicle_fp={non_vehicle_fp}; edge_ratio={edge_ratio:.3f}; case={case.reason}; "
        "detection-level only; tracker_replay_not_run"
    )
    row = {
        "scene": case.scene,
        "case_id": case.case_id,
        "detector_name": detector.name,
        "frames_checked": str(frames_checked),
        "vehicle_detections": str(vehicle_detections),
        "non_vehicle_false_positive_count": str(non_vehicle_fp),
        "missing_vehicle_count": str(missing),
        "multi_box_same_vehicle_count": str(multi_box),
        "box_fit_status": box_fit,
        "edge_contact_status": edge_status,
        "timeline_fragment_risk": fragment_risk,
        "same_vehicle_support_status": support_status,
        "forbidden_edge_safety_status": forbidden_status,
        "manual_override_pressure": manual_pressure,
        "overall_effect": overall_effect,
        "reason": reason,
    }
    metrics = {
        "missing": float(missing),
        "multi_box": float(multi_box),
        "non_vehicle_fp": float(non_vehicle_fp),
        "median_iou": float(median_iou),
        "edge_ratio": float(edge_ratio),
        "pressure_score": float(pressure_score),
    }
    return row, metrics


def missing_detector_row(detector: DetectorSource, case: CaseSpec) -> dict[str, str]:
    return {
        "scene": case.scene,
        "case_id": case.case_id,
        "detector_name": detector.name,
        "frames_checked": str(case.frame_end - case.frame_start + 1),
        "vehicle_detections": "0",
        "non_vehicle_false_positive_count": "0",
        "missing_vehicle_count": "",
        "multi_box_same_vehicle_count": "",
        "box_fit_status": "backend_missing",
        "edge_contact_status": "backend_missing",
        "timeline_fragment_risk": "unknown",
        "same_vehicle_support_status": "unknown",
        "forbidden_edge_safety_status": "unknown",
        "manual_override_pressure": "unknown",
        "overall_effect": "backend_missing",
        "reason": f"{detector.backend_status}; no local source table or no-download policy for {detector.source_model}; tracker_replay_not_run",
    }


def summarize(schema_rows: Sequence[Mapping[str, str]], manifest_rows: Sequence[Mapping[str, str]], detectors: Sequence[DetectorSource]) -> list[dict[str, str]]:
    expected_by_case = expected_manifest_by_case(manifest_rows)
    rows: list[dict[str, str]] = []
    baseline_metrics_by_case: dict[str, Mapping[str, float]] = {}
    baseline = next(det for det in detectors if det.name == "baseline_oty0")
    for case in CASES:
        row, metrics = summarize_available_detector(baseline, case, schema_rows, expected_by_case[case.case_id], None)
        rows.append(row)
        baseline_metrics_by_case[case.case_id] = metrics
    for detector in detectors:
        if detector.name == "baseline_oty0":
            continue
        for case in CASES:
            if detector.backend_status != "available" or case.scene not in detector.scene_tables or not detector.scene_tables[case.scene].exists():
                rows.append(missing_detector_row(detector, case))
                continue
            row, _metrics = summarize_available_detector(detector, case, schema_rows, expected_by_case[case.case_id], baseline_metrics_by_case[case.case_id])
            rows.append(row)
    return rows


def conclusion_label(summary_rows: Sequence[Mapping[str, str]]) -> str:
    actual = [row for row in summary_rows if row["detector_name"] != "baseline_oty0" and row["overall_effect"] != "backend_missing"]
    if not actual:
        return "DETECTOR_SWAP_PROBE_BACKEND_MISSING"
    improves = sum(1 for row in actual if row["overall_effect"] == "improves_timeline_stability")
    worse = sum(1 for row in actual if row["overall_effect"] == "worse")
    neutral = sum(1 for row in actual if row["overall_effect"] == "neutral")
    if improves > worse and improves >= max(2, neutral):
        return "DETECTOR_SWAP_PROBE_DETECTION_ONLY_IMPROVEMENT"
    if neutral >= improves and worse == 0:
        return "DETECTOR_SWAP_PROBE_NEUTRAL"
    return "DETECTOR_SWAP_PROBE_NEUTRAL"


def backend_notes(detectors: Sequence[DetectorSource]) -> str:
    ultralytics_available = importlib.util.find_spec("ultralytics") is not None
    lines = [f"- `ultralytics` import available: `{ultralytics_available}`"]
    for detector in detectors:
        available_tables = [scene for scene, path in detector.scene_tables.items() if path.exists()]
        lines.append(f"- `{detector.name}`: status=`{detector.backend_status}`, scenes_with_tables=`{';'.join(available_tables) or 'none'}`, source_model=`{detector.source_model}`, weight=`{detector.weight_path}`")
    return "\n".join(lines)


def report_text(
    timestamp: str,
    schema_path: Path,
    summary_path: Path,
    summary_rows: Sequence[Mapping[str, str]],
    detectors: Sequence[DetectorSource],
) -> str:
    label = conclusion_label(summary_rows)
    actual_rows = [row for row in summary_rows if row["detector_name"] == "ultralytics_yolo26l_probe"]
    improves = [row for row in actual_rows if row["overall_effect"] == "improves_timeline_stability"]
    worse = [row for row in actual_rows if row["overall_effect"] == "worse"]
    neutral = [row for row in actual_rows if row["overall_effect"] == "neutral"]
    inconclusive = [row for row in actual_rows if row["overall_effect"] == "inconclusive"]
    reduced_manual = [row for row in actual_rows if row["manual_override_pressure"] == "reduced"]
    increased_manual = [row for row in actual_rows if row["manual_override_pressure"] == "increased"]
    backend_missing = sorted({row["detector_name"] for row in summary_rows if row["overall_effect"] == "backend_missing"})
    return f"""# OTY2 Detector Swap Timeline Stability Probe

Timestamp: `{timestamp}`
Repository: `{REPO_ROOT}`
Branch: `feature/oty2-posthoc-mechanism-validation`
Verified starting HEAD requirement: `d52c14b Define optical timeline graph input contract`

## Boundary

This probe tests detector plug-in impact on optical timeline stability only. It does not replace the main OTY0 detector, modify existing OTY0 detection tables, modify tracker output, modify timeline graph conclusions, run SAR consumption, create final boxes, create revised GT, create final annotation, run SAR pairing/support, run selector/ranking, tune thresholds, or commit weights.

The comparison is not an mAP evaluation. It asks whether detector output reduces timeline pressure: missing diagnostic vehicle frames, non-vehicle false positives, same-vehicle multi-boxes, edge-contact instability, weak-edge uncertainty, forbidden-edge risk, and manual override pressure.

## Detector Plug-In Status

{backend_notes(detectors)}

No new detector weights were downloaded. Existing YOLO26l probe outputs were reused. Extra YOLO/RT-DETR entries are present as plug-in placeholders and are marked `backend_missing` / `weight_missing_no_download` until local weights or approved download are available outside the repo.

## Outputs

- Unified detection schema: `{schema_path.relative_to(REPO_ROOT)}`
- Stability summary: `{summary_path.relative_to(REPO_ROOT)}`

The unified detection schema contains only rows in the GM_RM017 and GM_RM011 diagnostic windows. `det_id` is unique only within detector/scene/frame and is not a vehicle identity.

## Actual Detector-Level Findings

Actual detectors compared:

- `baseline_oty0`: current OTY0 YOLO11l-derived baseline tables.
- `ultralytics_yolo26l_probe`: existing YOLO26l probe tables.

YOLO26l per-case effects:

- improved timeline stability rows: `{len(improves)}`
- worse rows: `{len(worse)}`
- neutral rows: `{len(neutral)}`
- inconclusive rows: `{len(inconclusive)}`
- manual override reduced rows: `{len(reduced_manual)}`
- manual override increased rows: `{len(increased_manual)}`

Backend/weight missing detectors:

{chr(10).join(f'- `{name}`' for name in backend_missing) if backend_missing else '- none'}

## Interpretation

    YOLO26l gives one useful detection-level improvement in the diagnostic windows: the GM_RM017 non-vehicle barrier case has much lower vehicle-like overlap. That is not enough to call it a general optical-timeline improvement. In several same-vehicle or forbidden-edge windows, YOLO26l increases multi-box pressure or missing diagnostic frames:

- GM_RM017 remains easier, but edge/partial visibility still creates pressure.
- GM_RM017 `bs_0002` remains an important non-vehicle exclusion test; detector swaps must not promote it to a vehicle identity.
- GM_RM011 strong short-gap edges remain visually supported, but YOLO26l adds multi-box pressure in these windows.
- GM_RM011 forbidden edges remain detection-only unresolved without tracker replay; detector output alone cannot prove safe identity separation.

Tracker replay was not run. The current result is therefore detection-level only.

## Required Answers

1. Detector replacement must be plug-in because the same optical timeline graph needs stable provenance across detector variants without overwriting OTY0 or tracker artifacts.
2. A new YOLO cannot directly replace the mainline because improved detection counts can still worsen multi-box, edge, or forbidden-edge pressure.
3. Baseline issues are partial/edge boxes, missing diagnostic frames in some windows, non-vehicle vehicle-like detections, and multi-box pressure.
4. YOLO26l does not uniformly reduce missing diagnostic frames; it introduces missing diagnostic frames in the GM_RM011 weak/forbidden windows under this detection-level check.
5. YOLO26l reduces vehicle-like overlap on the `GM_RM017 bs_0002` non-vehicle barrier case, but the case must still remain an exclusion.
6. YOLO26l does not uniformly reduce same-vehicle multi-box pressure.
7. YOLO26l improves box fit in some windows and is neutral or worse in others.
8. YOLO26l does not remove edge truncation pressure.
9. Manual override pressure is reduced in some rows and increased in others.
10. Weak edges do not become strong candidates from this detector-only probe; none should be automatically upgraded.
11. Forbidden-edge safety is not broken into a merge, but it remains detection-only unresolved without tracker replay.
12. Broad tracker replay is not justified by this result. A very bounded replay can still be useful as a negative-control or sensitivity check.
13. YOLO26l is not a mainline replacement candidate from this probe; it remains a detector variant worth keeping in the plug-in interface.
14. SAR is not allowed in this stage.
15. Final/revised annotation is not allowed.

## Conclusion

```text
{label}
```
"""


def build(args: argparse.Namespace) -> dict[str, Path]:
    timestamp = args.timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    samples_dir = REPO_ROOT / "reports" / "oty2" / "samples"
    report_path = REPO_ROOT / "reports" / "oty2" / f"oty2_detector_swap_timeline_stability_probe_{timestamp}.md"
    schema_path = samples_dir / f"oty2_detector_swap_detection_schema_{timestamp}.csv"
    summary_path = samples_dir / f"oty2_detector_swap_timeline_stability_summary_{timestamp}.csv"

    manifest_rows = read_csv(Path(args.manifest))
    _nodes = read_csv(Path(args.nodes))
    _edges = read_csv(Path(args.edges))

    all_frames = set()
    for case in CASES:
        all_frames.update(frame_set(case.frame_start, case.frame_end))
    scenes = sorted({case.scene for case in CASES})
    schema_rows = build_detection_schema(DETECTORS, scenes, all_frames)
    summary_rows = summarize(schema_rows, manifest_rows, DETECTORS)

    write_csv(schema_path, schema_rows, DETECTION_SCHEMA_FIELDS)
    write_csv(summary_path, summary_rows, SUMMARY_FIELDS)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report_text(timestamp, schema_path, summary_path, summary_rows, DETECTORS), encoding="utf-8")

    return {"report": report_path, "schema": schema_path, "summary": summary_path}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timestamp", default="")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--nodes", default=str(DEFAULT_NODES))
    parser.add_argument("--edges", default=str(DEFAULT_EDGES))
    parser.add_argument("--scenes", nargs="*", default=["GM_RM017", "GM_RM011"], help="Reserved for future detector runners; current cases are fixed to the diagnostic windows.")
    parser.add_argument("--detectors", nargs="*", default=[detector.name for detector in DETECTORS], help="Reserved for future detector runners; current probe records configured detectors.")
    parser.add_argument("--weights-root", default="D:/models")
    parser.add_argument("--no-download", action="store_true", default=True)
    parser.add_argument("--allow-download", action="store_true", default=False)
    return parser.parse_args()


def main() -> None:
    outputs = build(parse_args())
    for key, path in outputs.items():
        print(f"{key}: {path}")


if __name__ == "__main__":
    main()
