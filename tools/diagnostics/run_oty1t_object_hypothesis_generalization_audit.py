"""Run OTY1t-P4G generalized object-level optical hypothesis audit.

P4G generalizes the P4 object-hypothesis layer from one local case to available
scenes. It consumes runtime-safe optical artifacts only: OTY0 detections, OTY1
tracklet state rows, OTY1a fragment-review hints, and OTY1t tracker outputs.
It prepares object-level OTY2 input tables but does not implement OTY2, SAR
alignment, SAR band generation, SAR GT coverage, SAR evidence sampling,
selector/G2/A008 scoring, threshold tuning, training, or annotation proposal.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.optical_state.object_hypothesis import (  # noqa: E402
    GENERALIZED_OBJECT_FRAME_STATE_FIELDS,
    GENERALIZED_OBJECT_HYPOTHESIS_FIELDS,
    ORPHAN_OBSERVATION_FIELDS,
    ObjectHypothesisConfig,
    build_generalization_summary,
    build_generalized_object_frame_state_timeseries,
    build_generalized_object_hypotheses,
    build_orphan_observations,
    object_generalization_scene_summary,
    render_ambiguity_report,
    render_generalization_overview_svg,
    render_generalization_summary_markdown,
    safe_int,
)
from src.optical_state.observation_cluster import (  # noqa: E402
    BBOX_PROVENANCE_FIELDS,
    OBSERVATION_CLUSTER_FIELDS,
    ObservationClusterConfig,
    build_same_frame_observation_clusters,
    build_tracker_bbox_provenance_audit,
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


@dataclass
class SceneInputs:
    scene: str
    detection_table: Path
    oty1_dir: Path
    oty1a_dir: Path
    oty1t_dir: Path


@dataclass
class SceneRunResult:
    scene: str
    input_status: str
    blockers: list[str]
    object_rows: list[dict[str, Any]]
    frame_rows: list[dict[str, Any]]
    orphan_rows: list[dict[str, Any]]
    cluster_rows: list[dict[str, Any]]
    provenance_rows: list[dict[str, Any]]
    scene_summary: dict[str, Any]
    input_paths: dict[str, str]


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


def available_scenes(output_root: str | Path) -> list[str]:
    root = Path(output_root)
    scenes: set[str] = set()
    if not root.exists():
        return []
    for output_dir in root.glob("oty0_yolo_detection_stream_audit_*"):
        table = output_dir / "oty0_yolo_detection_table.csv"
        if table.exists():
            scene = _detection_table_scene(table)
            if scene:
                scenes.add(scene)
    return sorted(scenes)


def resolve_scene_inputs(scene: str, output_root: str | Path, tracker: str) -> tuple[SceneInputs | None, list[str]]:
    blockers: list[str] = []
    detection_table = latest_oty0_detection_table(output_root, scene)
    oty1_dir = latest_output_dir(output_root, "oty1_optical_tracklet_audit", "oty1_summary.json", scene)
    oty1a_dir = latest_output_dir(output_root, "oty1a_fragment_merge_audit", "oty1a_summary.json", scene)
    oty1t_dir = latest_tracker_output_dir(output_root, scene, tracker)
    if detection_table is None:
        blockers.append("missing_oty0_detection_table")
    if oty1_dir is None:
        blockers.append("missing_oty1_output_dir")
    if oty1a_dir is None:
        blockers.append("missing_oty1a_output_dir")
    if oty1t_dir is None:
        blockers.append("missing_oty1t_tracker_output_dir")
    if blockers or detection_table is None or oty1_dir is None or oty1a_dir is None or oty1t_dir is None:
        return None, blockers
    return SceneInputs(scene, detection_table, oty1_dir, oty1a_dir, oty1t_dir), blockers


def blocked_scene_result(scene: str, blockers: Sequence[str]) -> SceneRunResult:
    scene_summary = object_generalization_scene_summary(
        scene=scene,
        input_status="blocked",
        object_rows=[],
        frame_rows=[],
        orphan_rows=[],
        blockers=list(blockers),
    )
    return SceneRunResult(
        scene=scene,
        input_status="blocked",
        blockers=list(blockers),
        object_rows=[],
        frame_rows=[],
        orphan_rows=[],
        cluster_rows=[],
        provenance_rows=[],
        scene_summary=scene_summary,
        input_paths={},
    )


def run_scene(scene: str, args: argparse.Namespace) -> SceneRunResult:
    inputs, blockers = resolve_scene_inputs(scene, args.output_root, args.tracker)
    if inputs is None:
        return blocked_scene_result(scene, blockers)

    detection_rows = read_csv_rows(inputs.detection_table)
    forbidden = forbidden_input_fields(list(detection_rows[0].keys()) if detection_rows else [])
    if forbidden:
        return blocked_scene_result(scene, ["forbidden_runtime_field:" + ",".join(forbidden)])

    oty1_state_rows = read_csv_rows(inputs.oty1_dir / "oty1_optical_tracklet_state_timeseries.csv")
    merge_edges = read_csv_rows(inputs.oty1a_dir / "oty1a_fragment_merge_candidate_edges.csv")
    tracks = read_csv_rows(inputs.oty1t_dir / "oty1t_tracker_tracks.csv")
    assignment_rows = read_csv_rows(inputs.oty1t_dir / "oty1t_tracker_detection_assignments.csv")

    cluster_config = ObservationClusterConfig(scene=scene, tracker_name=args.tracker)
    cluster_rows = build_same_frame_observation_clusters(detection_rows, oty1_state_rows, assignment_rows, cluster_config)
    provenance_rows = build_tracker_bbox_provenance_audit(detection_rows, assignment_rows, cluster_config)
    config = ObjectHypothesisConfig(scene=scene, case_id=args.case, tracker_name=args.tracker)
    object_rows = build_generalized_object_hypotheses(
        tracks=tracks,
        assignment_rows=assignment_rows,
        oty1_state_rows=oty1_state_rows,
        merge_edges=merge_edges,
        cluster_rows=cluster_rows,
        provenance_rows=provenance_rows,
        config=config,
    )
    frame_rows = build_generalized_object_frame_state_timeseries(
        object_rows=object_rows,
        assignment_rows=assignment_rows,
        detection_rows=detection_rows,
        oty1_state_rows=oty1_state_rows,
        cluster_rows=cluster_rows,
        provenance_rows=provenance_rows,
        config=config,
    )
    orphan_rows = build_orphan_observations(
        detection_rows=detection_rows,
        assignment_rows=assignment_rows,
        oty1_state_rows=oty1_state_rows,
        cluster_rows=cluster_rows,
        object_rows=object_rows,
        config=config,
    )
    scene_summary = object_generalization_scene_summary(
        scene=scene,
        input_status="completed",
        object_rows=object_rows,
        frame_rows=frame_rows,
        orphan_rows=orphan_rows,
        blockers=[],
    )
    return SceneRunResult(
        scene=scene,
        input_status="completed",
        blockers=[],
        object_rows=object_rows,
        frame_rows=frame_rows,
        orphan_rows=orphan_rows,
        cluster_rows=cluster_rows,
        provenance_rows=provenance_rows,
        scene_summary=scene_summary,
        input_paths={
            "oty0_detection_table": str(inputs.detection_table),
            "oty1_output_dir": str(inputs.oty1_dir),
            "oty1a_output_dir": str(inputs.oty1a_dir),
            "oty1t_output_dir": str(inputs.oty1t_dir),
        },
    )


def sample_object_rows(rows: Sequence[Mapping[str, Any]], max_rows: int) -> list[dict[str, Any]]:
    def priority(row: Mapping[str, Any]) -> tuple[int, int, int, str]:
        text = ";".join(str(value) for value in row.values())
        has_case = "oty1_tracklet_0039" in text or "bt_0098" in text
        is_gm17 = str(row.get("scene", "")) == "GM_RM017"
        with_secondary = bool(str(row.get("secondary_det_ids", "") or ""))
        return (0 if has_case else 1, 0 if is_gm17 else 1, 0 if with_secondary else 1, str(row.get("object_hypothesis_id", "")))

    return [dict(row) for row in sorted(rows, key=priority)[:max_rows]]


def sample_frame_rows(rows: Sequence[Mapping[str, Any]], max_rows: int) -> list[dict[str, Any]]:
    key_frames = {149, 162, 163, 164, 165, 166, 167, 168, 171, 172, 173, 174, 181, 182}

    def priority(row: Mapping[str, Any]) -> tuple[int, int, int, str]:
        text = ";".join(str(value) for value in row.values())
        has_case = "bt_0098" in text or "GM_RM019_000172_001" in text or "GM_RM019_000172_002" in text
        is_gm17 = str(row.get("scene", "")) == "GM_RM017"
        frame = safe_int(row.get("optical_frame_num"))
        return (0 if has_case and frame in key_frames else 1, 0 if is_gm17 else 1, frame, text)

    return [dict(row) for row in sorted(rows, key=priority)[:max_rows]]


def sample_orphan_rows(rows: Sequence[Mapping[str, Any]], max_rows: int) -> list[dict[str, Any]]:
    def priority(row: Mapping[str, Any]) -> tuple[int, int, int, str]:
        is_gm17 = str(row.get("scene", "")) == "GM_RM017"
        frame = safe_int(row.get("optical_frame_num"))
        around_case = str(row.get("scene", "")) == "GM_RM019" and 160 <= frame <= 174
        return (0 if around_case else 1, 0 if is_gm17 else 1, frame, str(row.get("det_id", "")))

    return [dict(row) for row in sorted(rows, key=priority)[:max_rows]]


def write_report_artifacts(
    *,
    timestamp: str,
    summary: Mapping[str, Any],
    object_rows: Sequence[Mapping[str, Any]],
    frame_rows: Sequence[Mapping[str, Any]],
    orphan_rows: Sequence[Mapping[str, Any]],
    ambiguity_md: str,
    overview_svg: Path,
    max_sample_rows: int,
) -> dict[str, str]:
    report_dir = REPO_ROOT / "reports" / "oty1t"
    sample_dir = report_dir / "samples"
    viz_dir = sample_dir / "visualizations"
    report_dir.mkdir(parents=True, exist_ok=True)
    sample_dir.mkdir(parents=True, exist_ok=True)
    viz_dir.mkdir(parents=True, exist_ok=True)

    summary_md = report_dir / f"oty1t_object_hypothesis_generalization_summary_{timestamp}.md"
    summary_json = report_dir / f"oty1t_object_hypothesis_generalization_summary_{timestamp}.json"
    summary_md.write_text(render_generalization_summary_markdown(summary), encoding="utf-8")
    write_json(summary_json, summary)

    object_sample = sample_dir / "oty1t_object_hypotheses_generalized_sample.csv"
    frame_sample = sample_dir / "oty1t_object_frame_state_timeseries_generalized_sample.csv"
    orphan_sample = sample_dir / "oty1t_object_orphan_observations_sample.csv"
    ambiguity_sample = sample_dir / "oty1t_object_ambiguity_report.md"
    overview_sample = viz_dir / "oty1t_object_generalization_overview.svg"
    write_csv(object_sample, sample_object_rows(object_rows, max_sample_rows), GENERALIZED_OBJECT_HYPOTHESIS_FIELDS)
    write_csv(frame_sample, sample_frame_rows(frame_rows, max_sample_rows), GENERALIZED_OBJECT_FRAME_STATE_FIELDS)
    write_csv(orphan_sample, sample_orphan_rows(orphan_rows, max_sample_rows), ORPHAN_OBSERVATION_FIELDS)
    ambiguity_sample.write_text(ambiguity_md, encoding="utf-8")
    if overview_svg.exists():
        overview_sample.write_text(overview_svg.read_text(encoding="utf-8"), encoding="utf-8")
    return {
        "summary_md": str(summary_md),
        "summary_json": str(summary_json),
        "object_hypotheses_generalized_sample": str(object_sample),
        "object_frame_state_timeseries_generalized_sample": str(frame_sample),
        "object_orphan_observations_sample": str(orphan_sample),
        "object_ambiguity_report_sample": str(ambiguity_sample),
        "object_generalization_overview_svg": str(overview_sample),
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    timestamp = args.timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    scenes = available_scenes(args.output_root) if args.all_available_scenes else [args.scene]
    if not scenes:
        scenes = [args.scene]
    output_dir = Path(args.output_root) / f"oty1t_object_hypothesis_generalization_audit_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    scene_results = [run_scene(scene, args) for scene in scenes]

    object_rows = [row for result in scene_results for row in result.object_rows]
    frame_rows = [row for result in scene_results for row in result.frame_rows]
    orphan_rows = [row for result in scene_results for row in result.orphan_rows]
    cluster_rows = [row for result in scene_results for row in result.cluster_rows]
    provenance_rows = [row for result in scene_results for row in result.provenance_rows]
    scene_summaries = [result.scene_summary for result in scene_results]
    generated_at = datetime.now().isoformat(timespec="seconds")
    summary = build_generalization_summary(
        generated_at=generated_at,
        tracker_name=args.tracker,
        scenes_attempted=scenes,
        scene_summaries=scene_summaries,
        object_rows=object_rows,
        frame_rows=frame_rows,
        orphan_rows=orphan_rows,
        output_dir=str(output_dir),
    )
    summary["timestamp"] = timestamp
    summary["input_paths_by_scene"] = {result.scene: result.input_paths for result in scene_results}

    ambiguity_md = render_ambiguity_report(
        scene_summaries=scene_summaries,
        object_rows=object_rows,
        orphan_rows=orphan_rows,
        cluster_rows=cluster_rows,
    )
    overview_svg = output_dir / "visualizations" / "oty1t_object_generalization_overview.svg"
    render_generalization_overview_svg(overview_svg, summary)

    write_csv(output_dir / "oty1t_object_hypotheses_generalized.csv", object_rows, GENERALIZED_OBJECT_HYPOTHESIS_FIELDS)
    write_csv(output_dir / "oty1t_object_frame_state_timeseries_generalized.csv", frame_rows, GENERALIZED_OBJECT_FRAME_STATE_FIELDS)
    write_csv(output_dir / "oty1t_object_orphan_observations.csv", orphan_rows, ORPHAN_OBSERVATION_FIELDS)
    write_csv(output_dir / "oty1t_same_frame_observation_clusters_generalized.csv", cluster_rows, OBSERVATION_CLUSTER_FIELDS)
    write_csv(output_dir / "oty1t_tracker_bbox_provenance_generalized.csv", provenance_rows, BBOX_PROVENANCE_FIELDS)
    (output_dir / "oty1t_object_ambiguity_report.md").write_text(ambiguity_md, encoding="utf-8")

    report_artifacts = write_report_artifacts(
        timestamp=timestamp,
        summary=summary,
        object_rows=object_rows,
        frame_rows=frame_rows,
        orphan_rows=orphan_rows,
        ambiguity_md=ambiguity_md,
        overview_svg=overview_svg,
        max_sample_rows=args.max_sample_rows,
    )
    summary["artifacts"] = {
        "object_hypotheses_generalized": str(output_dir / "oty1t_object_hypotheses_generalized.csv"),
        "object_frame_state_timeseries_generalized": str(output_dir / "oty1t_object_frame_state_timeseries_generalized.csv"),
        "object_orphan_observations": str(output_dir / "oty1t_object_orphan_observations.csv"),
        "object_ambiguity_report": str(output_dir / "oty1t_object_ambiguity_report.md"),
        "object_generalization_overview_svg": str(overview_svg),
        **report_artifacts,
    }
    write_json(output_dir / "oty1t_object_hypothesis_generalization_summary.json", summary)
    (output_dir / "oty1t_object_hypothesis_generalization_summary.md").write_text(
        render_generalization_summary_markdown(summary), encoding="utf-8"
    )
    write_json(REPO_ROOT / "reports" / "oty1t" / f"oty1t_object_hypothesis_generalization_summary_{timestamp}.json", summary)
    (REPO_ROOT / "reports" / "oty1t" / f"oty1t_object_hypothesis_generalization_summary_{timestamp}.md").write_text(
        render_generalization_summary_markdown(summary), encoding="utf-8"
    )
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", default="GM_RM019")
    parser.add_argument("--case", default="0039_0045")
    parser.add_argument("--tracker", default="bytetrack")
    parser.add_argument("--output-root", default="outputs")
    parser.add_argument("--timestamp", default="")
    parser.add_argument("--max-sample-rows", type=int, default=120)
    parser.add_argument("--all-available-scenes", action="store_true")
    return parser


def main() -> None:
    summary = run(build_parser().parse_args())
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
