"""Run OTY1t-P3 observation-cluster and association-choice audit.

This runner consumes runtime-safe optical artifacts only: OTY0 YOLO detections,
OTY1 optical state rows, OTY1a optical merge-review context, and OTY1t tracker
assignment rows. It writes review-only optical hypotheses for same-frame
observation clusters, tracker association choices, and tracker bbox provenance.
It does not enter OTY2, SAR alignment, SAR band generation, SAR GT coverage,
SAR evidence sampling, selector/G2/A008 scoring, threshold tuning, training, or
annotation proposal.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.optical_state.observation_cluster import (  # noqa: E402
    ASSOCIATION_CHOICE_FIELDS,
    BBOX_PROVENANCE_FIELDS,
    OBSERVATION_CLUSTER_FIELDS,
    ObservationClusterConfig,
    build_association_choice_audit,
    build_same_frame_observation_clusters,
    build_summary,
    build_tracker_bbox_provenance_audit,
    find_case_bridge_pair,
    hypothesis_rows,
    local_window_explanations_payload,
    merge_edge_for_case,
    pair_metrics,
    render_association_choice_svg,
    render_bbox_provenance_svg,
    render_explanations_markdown,
    render_observation_clusters_svg,
    render_summary_markdown,
    safe_int,
)


FORBIDDEN_RUNTIME_TOKENS = (
    "gt",
    "final",
    "manual",
    "oracle",
    "review_queue",
    "sar_",
    "posthoc",
    "target_identity",
    "selector",
    "g2",
    "a008",
    "threshold",
    "training",
    "proposal",
)


def _is_duplicate_header_row(row: Mapping[str, Any]) -> bool:
    hits = 0
    values = 0
    for key, value in row.items():
        text = str(value or "").strip()
        if not text:
            continue
        values += 1
        if text == key:
            hits += 1
    return values > 0 and hits >= max(2, values // 2)


def read_csv_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    return [row for row in rows if not _is_duplicate_header_row(row)]


def write_csv(path: str | Path, rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def read_json(path: str | Path) -> dict[str, Any]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def write_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def forbidden_input_fields(fieldnames: Sequence[str]) -> list[str]:
    out: list[str] = []
    for field in fieldnames:
        lower = str(field).lower()
        if any(token in lower for token in FORBIDDEN_RUNTIME_TOKENS):
            out.append(str(field))
    return out


def _summary_scene(output_dir: Path, summary_name: str) -> str:
    summary = read_json(output_dir / summary_name)
    return str(summary.get("scene", "") or "").strip()


def _detection_table_scene(table: Path) -> str:
    summary = read_json(table.parent / "oty0_summary.json")
    scene = str(summary.get("scene", "") or "").strip()
    if scene:
        return scene
    try:
        with table.open("r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                return str(row.get("scene", "") or "").strip()
    except OSError:
        return ""
    return ""


def latest_oty0_detection_table(output_root: str | Path, scene: str) -> Path | None:
    root = Path(output_root)
    if not root.exists():
        return None
    for output_dir in sorted(root.glob("oty0_yolo_detection_stream_audit_*"), key=lambda path: path.name, reverse=True):
        table = output_dir / "oty0_yolo_detection_table.csv"
        if table.exists() and _detection_table_scene(table) == scene:
            return table
    return None


def latest_output_dir(output_root: str | Path, prefix: str, summary_name: str, scene: str) -> Path | None:
    root = Path(output_root)
    if not root.exists():
        return None
    for output_dir in sorted(root.glob(f"{prefix}_*"), key=lambda path: path.name, reverse=True):
        if (output_dir / summary_name).exists() and _summary_scene(output_dir, summary_name) == scene:
            return output_dir
    return None


def latest_tracker_output_dir(output_root: str | Path, scene: str, tracker: str) -> Path | None:
    root = Path(output_root)
    if not root.exists():
        return None
    patterns = [f"oty1t_tracker_audit_{tracker}_*", "oty1t_tracker_audit_*"]
    seen: set[Path] = set()
    for pattern in patterns:
        for output_dir in sorted(root.glob(pattern), key=lambda path: path.name, reverse=True):
            if output_dir in seen:
                continue
            seen.add(output_dir)
            summary = read_json(output_dir / "oty1t_summary.json")
            if str(summary.get("scene", "") or "") != scene:
                continue
            if str(summary.get("tracker_name", "") or tracker) != tracker:
                continue
            if (output_dir / "oty1t_tracker_detection_assignments.csv").exists():
                return output_dir
    return None


def require_path(path: Path | None, message: str) -> Path:
    if path is None or not path.exists():
        raise FileNotFoundError(message)
    return path


def scene_sample_rows(rows: Sequence[Mapping[str, Any]], max_rows: int) -> list[dict[str, Any]]:
    key_dets = {
        "GM_RM019_000172_001",
        "GM_RM019_000172_002",
        "GM_RM019_000173_001",
        "GM_RM019_000174_001",
        "GM_RM019_000181_001",
        "GM_RM019_000182_001",
    }

    def priority(row: Mapping[str, Any]) -> tuple[int, int, str]:
        text = ";".join(str(value) for value in row.values())
        has_key = any(det_id in text for det_id in key_dets)
        frame = safe_int(row.get("optical_frame_num"))
        cluster_size = safe_int(row.get("cluster_size"))
        return (0 if has_key else 1, 0 if cluster_size > 1 else 1, frame, text)

    return [dict(row) for row in sorted(rows, key=priority)[:max_rows]]


def write_report_artifacts(
    timestamp: str,
    summary: Mapping[str, Any],
    cluster_rows: Sequence[Mapping[str, Any]],
    association_rows: Sequence[Mapping[str, Any]],
    provenance_rows: Sequence[Mapping[str, Any]],
    explanation_md: str,
    local_viz_dir: Path,
    max_sample_rows: int,
) -> dict[str, str]:
    report_dir = REPO_ROOT / "reports" / "oty1t"
    sample_dir = report_dir / "samples"
    panel_dir = sample_dir / "visualizations" / "oty1t_0039_0045_frame_panels"
    report_dir.mkdir(parents=True, exist_ok=True)
    sample_dir.mkdir(parents=True, exist_ok=True)
    panel_dir.mkdir(parents=True, exist_ok=True)

    hypotheses = hypothesis_rows(summary, {})
    summary_md = report_dir / f"oty1t_observation_cluster_summary_{timestamp}.md"
    summary_json = report_dir / f"oty1t_observation_cluster_summary_{timestamp}.json"
    summary_md.write_text(render_summary_markdown(summary, hypotheses), encoding="utf-8")
    write_json(summary_json, summary)

    cluster_sample = sample_dir / "oty1t_same_frame_observation_clusters_sample.csv"
    association_sample = sample_dir / "oty1t_association_choice_audit_sample.csv"
    provenance_sample = sample_dir / "oty1t_tracker_bbox_provenance_audit_sample.csv"
    explanation_sample = sample_dir / "oty1t_0039_0045_local_window_explanations.md"
    write_csv(cluster_sample, scene_sample_rows(cluster_rows, max_sample_rows), OBSERVATION_CLUSTER_FIELDS)
    write_csv(association_sample, scene_sample_rows(association_rows, max_sample_rows), ASSOCIATION_CHOICE_FIELDS)
    write_csv(provenance_sample, scene_sample_rows(provenance_rows, max_sample_rows), BBOX_PROVENANCE_FIELDS)
    explanation_sample.write_text(explanation_md, encoding="utf-8")

    viz_artifacts: dict[str, str] = {}
    for name in (
        "gm_rm019_0039_0045_observation_clusters_162_174.svg",
        "gm_rm019_0039_0045_association_choice_172.svg",
        "gm_rm019_0039_0045_bbox_provenance_172_183.svg",
    ):
        source = local_viz_dir / name
        target = panel_dir / name
        if source.exists():
            target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
            viz_artifacts[name] = str(target)

    return {
        "summary_md": str(summary_md),
        "summary_json": str(summary_json),
        "cluster_sample": str(cluster_sample),
        "association_sample": str(association_sample),
        "provenance_sample": str(provenance_sample),
        "explanation_sample": str(explanation_sample),
        **viz_artifacts,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    timestamp = args.timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    config = ObservationClusterConfig(
        scene=args.scene,
        tracker_name=args.tracker,
        case_id=args.case,
        frame_start=args.frame_start,
        frame_end=args.frame_end,
        same_class_iou_threshold=args.same_class_iou_threshold,
        same_class_center_distance_px=args.same_class_center_distance_px,
        containment_threshold=args.containment_threshold,
        contact_margin_px=args.contact_margin_px,
    )
    output_dir = Path(args.output_root) / f"oty1t_observation_cluster_audit_{timestamp}"
    viz_dir = output_dir / "visualizations"
    output_dir.mkdir(parents=True, exist_ok=True)
    viz_dir.mkdir(parents=True, exist_ok=True)

    detection_table = Path(args.oty0_detection_table) if args.oty0_detection_table else latest_oty0_detection_table(args.output_root, args.scene)
    detection_table = require_path(detection_table, f"No OTY0 detection table found for {args.scene}")
    oty1_dir = Path(args.oty1_output_dir) if args.oty1_output_dir else latest_output_dir(args.output_root, "oty1_optical_tracklet_audit", "oty1_summary.json", args.scene)
    oty1_dir = require_path(oty1_dir, f"No OTY1 output dir found for {args.scene}")
    oty1a_dir = Path(args.oty1a_output_dir) if args.oty1a_output_dir else latest_output_dir(args.output_root, "oty1a_fragment_merge_audit", "oty1a_summary.json", args.scene)
    oty1a_dir = require_path(oty1a_dir, f"No OTY1a output dir found for {args.scene}")
    oty1t_dir = Path(args.oty1t_output_dir) if args.oty1t_output_dir else latest_tracker_output_dir(args.output_root, args.scene, args.tracker)
    oty1t_dir = require_path(oty1t_dir, f"No OTY1t tracker output dir found for {args.scene}/{args.tracker}")

    detection_rows = read_csv_rows(detection_table)
    forbidden = forbidden_input_fields(list(detection_rows[0].keys()) if detection_rows else [])
    if forbidden:
        raise ValueError("OTY0 detection table contains forbidden runtime-looking fields: " + ", ".join(forbidden))
    oty1_state_rows = read_csv_rows(oty1_dir / "oty1_optical_tracklet_state_timeseries.csv")
    oty1a_edges = read_csv_rows(oty1a_dir / "oty1a_fragment_merge_candidate_edges.csv")
    assignment_rows = read_csv_rows(oty1t_dir / "oty1t_tracker_detection_assignments.csv")

    cluster_rows = build_same_frame_observation_clusters(detection_rows, oty1_state_rows, assignment_rows, config)
    association_rows = build_association_choice_audit(cluster_rows, detection_rows, oty1_state_rows, assignment_rows, config)
    provenance_rows = build_tracker_bbox_provenance_audit(detection_rows, assignment_rows, config)
    bridge_pair = find_case_bridge_pair(detection_rows, oty1_state_rows, config)
    merge_edge = merge_edge_for_case(oty1a_edges, config)
    pair_172_001_173_001 = pair_metrics(detection_rows, "GM_RM019_000172_001", "GM_RM019_000173_001")
    pair_172_002_173_001 = pair_metrics(detection_rows, "GM_RM019_000172_002", "GM_RM019_000173_001")

    summary = build_summary(
        cluster_rows,
        association_rows,
        provenance_rows,
        bridge_pair,
        pair_172_001_173_001,
        pair_172_002_173_001,
        config,
        str(output_dir),
    )
    summary["generated_at"] = datetime.now().isoformat(timespec="seconds")
    summary["timestamp"] = timestamp
    summary["input_oty0_detection_table"] = str(detection_table)
    summary["input_oty1_output_dir"] = str(oty1_dir)
    summary["input_oty1a_output_dir"] = str(oty1a_dir)
    summary["input_oty1t_output_dir"] = str(oty1t_dir)
    summary["audit_config"] = {
        "same_class_iou_threshold": config.same_class_iou_threshold,
        "same_class_center_distance_px": config.same_class_center_distance_px,
        "containment_threshold": config.containment_threshold,
        "contact_margin_px": config.contact_margin_px,
        "frame_start": config.frame_start,
        "frame_end": config.frame_end,
    }

    explanation_payload = local_window_explanations_payload(summary, merge_edge)
    explanation_md = render_explanations_markdown(explanation_payload)
    hypotheses = explanation_payload.get("hypotheses", [])
    if isinstance(hypotheses, list):
        summary["hypothesis_support"] = {
            str(row.get("hypothesis_name", "")): {
                "support_level": row.get("support_level", ""),
                "recommended_use": row.get("recommended_use", ""),
            }
            for row in hypotheses
            if isinstance(row, Mapping)
        }

    write_csv(output_dir / "oty1t_same_frame_observation_clusters.csv", cluster_rows, OBSERVATION_CLUSTER_FIELDS)
    write_csv(output_dir / "oty1t_association_choice_audit.csv", association_rows, ASSOCIATION_CHOICE_FIELDS)
    write_csv(output_dir / "oty1t_tracker_bbox_provenance_audit.csv", provenance_rows, BBOX_PROVENANCE_FIELDS)
    write_json(output_dir / "oty1t_0039_0045_local_window_explanations.json", explanation_payload)
    (output_dir / "oty1t_0039_0045_local_window_explanations.md").write_text(explanation_md, encoding="utf-8")

    cluster_svg = viz_dir / "gm_rm019_0039_0045_observation_clusters_162_174.svg"
    association_svg = viz_dir / "gm_rm019_0039_0045_association_choice_172.svg"
    provenance_svg = viz_dir / "gm_rm019_0039_0045_bbox_provenance_172_183.svg"
    render_observation_clusters_svg(cluster_svg, cluster_rows, association_rows)
    render_association_choice_svg(association_svg, detection_rows, assignment_rows)
    render_bbox_provenance_svg(provenance_svg, provenance_rows)

    report_artifacts = write_report_artifacts(
        timestamp,
        summary,
        cluster_rows,
        association_rows,
        provenance_rows,
        explanation_md,
        viz_dir,
        args.max_sample_rows,
    )
    summary["artifacts"] = {
        "observation_clusters": str(output_dir / "oty1t_same_frame_observation_clusters.csv"),
        "association_choice_audit": str(output_dir / "oty1t_association_choice_audit.csv"),
        "bbox_provenance_audit": str(output_dir / "oty1t_tracker_bbox_provenance_audit.csv"),
        "local_window_explanations_md": str(output_dir / "oty1t_0039_0045_local_window_explanations.md"),
        "local_window_explanations_json": str(output_dir / "oty1t_0039_0045_local_window_explanations.json"),
        "observation_clusters_svg": str(cluster_svg),
        "association_choice_svg": str(association_svg),
        "bbox_provenance_svg": str(provenance_svg),
        **report_artifacts,
    }
    write_json(output_dir / "oty1t_observation_cluster_summary.json", summary)
    (output_dir / "oty1t_observation_cluster_summary.md").write_text(
        render_summary_markdown(summary, hypothesis_rows(summary, merge_edge)),
        encoding="utf-8",
    )
    write_json(REPO_ROOT / "reports" / "oty1t" / f"oty1t_observation_cluster_summary_{timestamp}.json", summary)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", default="GM_RM019")
    parser.add_argument("--tracker", default="bytetrack")
    parser.add_argument("--case", default="0039_0045")
    parser.add_argument("--oty0-detection-table", default="")
    parser.add_argument("--oty1-output-dir", default="")
    parser.add_argument("--oty1a-output-dir", default="")
    parser.add_argument("--oty1t-output-dir", default="")
    parser.add_argument("--output-root", default="outputs")
    parser.add_argument("--timestamp", default="")
    parser.add_argument("--frame-start", type=int, default=149)
    parser.add_argument("--frame-end", type=int, default=183)
    parser.add_argument("--same-class-iou-threshold", type=float, default=0.25)
    parser.add_argument("--same-class-center-distance-px", type=float, default=120.0)
    parser.add_argument("--containment-threshold", type=float, default=0.50)
    parser.add_argument("--contact-margin-px", type=float, default=2.0)
    parser.add_argument("--max-sample-rows", type=int, default=80)
    return parser


def main() -> None:
    summary = run(build_parser().parse_args())
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
