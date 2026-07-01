"""Run OTY1t-P4 object-level observation-track hypothesis audit.

P4 reads runtime-safe optical outputs from OTY0, OTY1, OTY1a, OTY1t tracker
audit, and OTY1t-P3 observation-cluster audit. It builds object-level optical
hypotheses that combine a main tracker trajectory with primary detections,
secondary observations, same-frame clusters, and fragment-review hints. It
does not enter OTY2, SAR alignment, SAR band generation, SAR GT coverage,
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

from src.optical_state.object_hypothesis import (  # noqa: E402
    OBJECT_FRAME_STATE_FIELDS,
    OBJECT_HYPOTHESIS_FIELDS,
    ObjectHypothesisConfig,
    build_object_frame_state_timeseries,
    build_object_hypotheses,
    build_summary,
    evidence_payload,
    join_values,
    related_edges_for_tracklets,
    render_evidence_markdown,
    render_object_graph_svg,
    render_summary_markdown,
    safe_int,
    split_values,
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


def latest_p3_output_dir(output_root: str | Path, scene: str, case_id: str) -> Path | None:
    root = Path(output_root)
    if not root.exists():
        return None
    for output_dir in sorted(root.glob("oty1t_observation_cluster_audit_*"), key=lambda path: path.name, reverse=True):
        summary = read_json(output_dir / "oty1t_observation_cluster_summary.json")
        if str(summary.get("scene", "") or "") == scene and str(summary.get("case_id", "") or "") == case_id:
            if (output_dir / "oty1t_same_frame_observation_clusters.csv").exists():
                return output_dir
    return None


def require_path(path: Path | None, message: str) -> Path:
    if path is None or not path.exists():
        raise FileNotFoundError(message)
    return path


def sample_object_rows(rows: Sequence[Mapping[str, Any]], max_rows: int) -> list[dict[str, Any]]:
    return [dict(row) for row in rows[:max_rows]]


def sample_frame_rows(rows: Sequence[Mapping[str, Any]], max_rows: int) -> list[dict[str, Any]]:
    priority_frames = {149, 162, 163, 164, 165, 166, 167, 168, 171, 172, 173, 174, 181, 182, 183}

    def priority(row: Mapping[str, Any]) -> tuple[int, int]:
        frame = safe_int(row.get("optical_frame_num"))
        return (0 if frame in priority_frames else 1, frame)

    return [dict(row) for row in sorted(rows, key=priority)[:max_rows]]


def write_report_artifacts(
    *,
    timestamp: str,
    summary: Mapping[str, Any],
    object_rows: Sequence[Mapping[str, Any]],
    frame_rows: Sequence[Mapping[str, Any]],
    evidence_md: str,
    graph_svg: Path,
    max_sample_rows: int,
) -> dict[str, str]:
    report_dir = REPO_ROOT / "reports" / "oty1t"
    sample_dir = report_dir / "samples"
    panel_dir = sample_dir / "visualizations" / "oty1t_0039_0045_frame_panels"
    report_dir.mkdir(parents=True, exist_ok=True)
    sample_dir.mkdir(parents=True, exist_ok=True)
    panel_dir.mkdir(parents=True, exist_ok=True)

    summary_md = report_dir / f"oty1t_object_hypothesis_summary_{timestamp}.md"
    summary_json = report_dir / f"oty1t_object_hypothesis_summary_{timestamp}.json"
    summary_md.write_text(render_summary_markdown(summary), encoding="utf-8")
    write_json(summary_json, summary)

    object_sample = sample_dir / "oty1t_object_hypotheses_sample.csv"
    frame_sample = sample_dir / "oty1t_object_frame_state_timeseries_sample.csv"
    evidence_sample = sample_dir / "oty1t_object_hypothesis_evidence.md"
    graph_sample = panel_dir / "gm_rm019_0039_0045_object_hypothesis_graph.svg"
    write_csv(object_sample, sample_object_rows(object_rows, max_sample_rows), OBJECT_HYPOTHESIS_FIELDS)
    write_csv(frame_sample, sample_frame_rows(frame_rows, max_sample_rows), OBJECT_FRAME_STATE_FIELDS)
    evidence_sample.write_text(evidence_md, encoding="utf-8")
    if graph_svg.exists():
        graph_sample.write_text(graph_svg.read_text(encoding="utf-8"), encoding="utf-8")
    return {
        "summary_md": str(summary_md),
        "summary_json": str(summary_json),
        "object_hypotheses_sample": str(object_sample),
        "object_frame_state_sample": str(frame_sample),
        "evidence_sample": str(evidence_sample),
        "object_graph_svg_sample": str(graph_sample),
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    timestamp = args.timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    config = ObjectHypothesisConfig(scene=args.scene, case_id=args.case, tracker_name=args.tracker)
    output_dir = Path(args.output_root) / f"oty1t_object_hypothesis_audit_{timestamp}"
    viz_dir = output_dir / "visualizations"
    output_dir.mkdir(parents=True, exist_ok=True)
    viz_dir.mkdir(parents=True, exist_ok=True)

    detection_table = Path(args.oty0_detection_table) if args.oty0_detection_table else latest_oty0_detection_table(args.output_root, args.scene)
    detection_table = require_path(detection_table, f"No OTY0 detection table found for {args.scene}")
    detection_rows = read_csv_rows(detection_table)
    forbidden = forbidden_input_fields(list(detection_rows[0].keys()) if detection_rows else [])
    if forbidden:
        raise ValueError("OTY0 detection table contains forbidden runtime-looking fields: " + ", ".join(forbidden))

    oty1_dir = Path(args.oty1_output_dir) if args.oty1_output_dir else latest_output_dir(args.output_root, "oty1_optical_tracklet_audit", "oty1_summary.json", args.scene)
    oty1_dir = require_path(oty1_dir, f"No OTY1 output dir found for {args.scene}")
    oty1a_dir = Path(args.oty1a_output_dir) if args.oty1a_output_dir else latest_output_dir(args.output_root, "oty1a_fragment_merge_audit", "oty1a_summary.json", args.scene)
    oty1a_dir = require_path(oty1a_dir, f"No OTY1a output dir found for {args.scene}")
    oty1t_dir = Path(args.oty1t_output_dir) if args.oty1t_output_dir else latest_tracker_output_dir(args.output_root, args.scene, args.tracker)
    oty1t_dir = require_path(oty1t_dir, f"No OTY1t tracker output dir found for {args.scene}/{args.tracker}")
    p3_dir = Path(args.p3_output_dir) if args.p3_output_dir else latest_p3_output_dir(args.output_root, args.scene, args.case)
    p3_dir = require_path(p3_dir, f"No OTY1t-P3 observation-cluster output dir found for {args.scene}/{args.case}")

    oty1_state_rows = read_csv_rows(oty1_dir / "oty1_optical_tracklet_state_timeseries.csv")
    merge_edges = read_csv_rows(oty1a_dir / "oty1a_fragment_merge_candidate_edges.csv")
    tracks = read_csv_rows(oty1t_dir / "oty1t_tracker_tracks.csv")
    assignment_rows = read_csv_rows(oty1t_dir / "oty1t_tracker_detection_assignments.csv")
    cluster_rows = read_csv_rows(p3_dir / "oty1t_same_frame_observation_clusters.csv")
    association_rows = read_csv_rows(p3_dir / "oty1t_association_choice_audit.csv")
    provenance_rows = read_csv_rows(p3_dir / "oty1t_tracker_bbox_provenance_audit.csv")
    p3_summary = read_json(p3_dir / "oty1t_observation_cluster_summary.json")

    object_rows = build_object_hypotheses(
        tracks=tracks,
        association_rows=association_rows,
        oty1_state_rows=oty1_state_rows,
        merge_edges=merge_edges,
        cluster_rows=cluster_rows,
        provenance_rows=provenance_rows,
        p3_summary=p3_summary,
        config=config,
    )
    frame_rows = build_object_frame_state_timeseries(
        object_rows=object_rows,
        association_rows=association_rows,
        oty1_state_rows=oty1_state_rows,
        cluster_rows=cluster_rows,
        provenance_rows=provenance_rows,
        config=config,
    )
    related_edge_count = 0
    if object_rows:
        related_edge_count = len(
            related_edges_for_tracklets(
                merge_edges,
                split_values(object_rows[0].get("primary_tracklet_ids")) + split_values(object_rows[0].get("secondary_tracklet_ids")),
                args.scene,
            )
        )
    summary = build_summary(object_rows, frame_rows, cluster_rows, related_edge_count)
    summary.update(
        {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "timestamp": timestamp,
            "output_dir": str(output_dir),
            "input_oty0_detection_table": str(detection_table),
            "input_oty1_output_dir": str(oty1_dir),
            "input_oty1a_output_dir": str(oty1a_dir),
            "input_oty1t_output_dir": str(oty1t_dir),
            "input_p3_output_dir": str(p3_dir),
        }
    )

    evidence = evidence_payload(object_rows, frame_rows, p3_summary)
    evidence_md = render_evidence_markdown(evidence)
    graph_svg = viz_dir / "gm_rm019_0039_0045_object_hypothesis_graph.svg"
    render_object_graph_svg(graph_svg, object_rows, frame_rows)

    write_csv(output_dir / "oty1t_object_hypotheses.csv", object_rows, OBJECT_HYPOTHESIS_FIELDS)
    write_csv(output_dir / "oty1t_object_frame_state_timeseries.csv", frame_rows, OBJECT_FRAME_STATE_FIELDS)
    write_json(output_dir / "oty1t_object_hypothesis_evidence.json", evidence)
    (output_dir / "oty1t_object_hypothesis_evidence.md").write_text(evidence_md, encoding="utf-8")
    write_json(output_dir / "oty1t_object_hypothesis_summary.json", summary)
    (output_dir / "oty1t_object_hypothesis_summary.md").write_text(render_summary_markdown(summary), encoding="utf-8")

    report_artifacts = write_report_artifacts(
        timestamp=timestamp,
        summary=summary,
        object_rows=object_rows,
        frame_rows=frame_rows,
        evidence_md=evidence_md,
        graph_svg=graph_svg,
        max_sample_rows=args.max_sample_rows,
    )
    summary["artifacts"] = {
        "object_hypotheses": str(output_dir / "oty1t_object_hypotheses.csv"),
        "object_frame_state_timeseries": str(output_dir / "oty1t_object_frame_state_timeseries.csv"),
        "object_hypothesis_evidence_md": str(output_dir / "oty1t_object_hypothesis_evidence.md"),
        "object_hypothesis_evidence_json": str(output_dir / "oty1t_object_hypothesis_evidence.json"),
        "object_graph_svg": str(graph_svg),
        **report_artifacts,
    }
    write_json(output_dir / "oty1t_object_hypothesis_summary.json", summary)
    write_json(REPO_ROOT / "reports" / "oty1t" / f"oty1t_object_hypothesis_summary_{timestamp}.json", summary)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", default="GM_RM019")
    parser.add_argument("--case", default="0039_0045")
    parser.add_argument("--tracker", default="bytetrack")
    parser.add_argument("--oty0-detection-table", default="")
    parser.add_argument("--oty1-output-dir", default="")
    parser.add_argument("--oty1a-output-dir", default="")
    parser.add_argument("--oty1t-output-dir", default="")
    parser.add_argument("--p3-output-dir", default="")
    parser.add_argument("--output-root", default="outputs")
    parser.add_argument("--timestamp", default="")
    parser.add_argument("--max-sample-rows", type=int, default=80)
    return parser


def main() -> None:
    summary = run(build_parser().parse_args())
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
