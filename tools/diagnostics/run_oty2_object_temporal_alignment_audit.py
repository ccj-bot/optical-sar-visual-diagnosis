"""Run OTY2-P0 object-level temporal alignment audit with readiness gating.

OTY2-P0 consumes OTY1t-P4G object-level optical hypotheses and object-frame
state rows. It writes temporal frame/window candidates only. It does not read
SAR image content, use SAR GT, generate SAR bands/corridors/boxes, sample SAR
evidence, use selector output, train thresholds, or create annotation
proposals.
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

from src.optical_state.object_temporal_alignment import (  # noqa: E402
    OBJECT_ALIGNMENT_FRAME_MAP_FIELDS,
    OBJECT_ALIGNMENT_WINDOW_CANDIDATE_FIELDS,
    OBJECT_READINESS_GATING_FIELDS,
    SCENE_INPUT_STATUS_FIELDS,
    build_object_alignment_frame_map_rows,
    build_object_alignment_window_candidate_rows,
    build_object_readiness_gating_rows,
    build_scene_input_status_rows,
    build_temporal_alignment_summary,
    render_overview_svg,
    render_temporal_alignment_summary_markdown,
    render_uncertainty_report,
    sample_frame_map_rows,
    sample_gating_rows,
    sample_window_rows,
    unique_ordered,
)


P4G_OBJECT_FILE = "oty1t_object_hypotheses_generalized.csv"
P4G_FRAME_FILE = "oty1t_object_frame_state_timeseries_generalized.csv"
P4G_ORPHAN_FILE = "oty1t_object_orphan_observations.csv"
P4G_SUMMARY_FILE = "oty1t_object_hypothesis_generalization_summary.json"


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
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def write_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def resolve_path(path_text: str | Path) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def latest_p4g_output_dir(output_root: str | Path) -> Path | None:
    root = resolve_path(output_root)
    if not root.exists():
        return None
    for output_dir in sorted(
        root.glob("oty1t_object_hypothesis_generalization_audit_*"),
        key=lambda path: path.name,
        reverse=True,
    ):
        if (output_dir / P4G_OBJECT_FILE).exists() and (output_dir / P4G_FRAME_FILE).exists():
            return output_dir
    return None


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
    root = resolve_path(output_root)
    if not root.exists():
        return None
    for output_dir in sorted(root.glob("oty0_yolo_detection_stream_audit_*"), key=lambda path: path.name, reverse=True):
        table = output_dir / "oty0_yolo_detection_table.csv"
        if table.exists() and _detection_table_scene(table) == scene:
            return table
    return None


def latest_output_dir(output_root: str | Path, prefix: str, summary_name: str, scene: str) -> Path | None:
    root = resolve_path(output_root)
    if not root.exists():
        return None
    for output_dir in sorted(root.glob(f"{prefix}_*"), key=lambda path: path.name, reverse=True):
        if (output_dir / summary_name).exists() and _summary_scene(output_dir, summary_name) == scene:
            return output_dir
    return None


def latest_tracker_output_dir(output_root: str | Path, scene: str, tracker: str) -> Path | None:
    root = resolve_path(output_root)
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


def stage_availability(output_root: str | Path, scene: str, tracker: str) -> dict[str, Any]:
    oty0 = latest_oty0_detection_table(output_root, scene)
    oty1 = latest_output_dir(output_root, "oty1_optical_tracklet_audit", "oty1_summary.json", scene)
    oty1a = latest_output_dir(output_root, "oty1a_fragment_merge_audit", "oty1a_summary.json", scene)
    oty1t = latest_tracker_output_dir(output_root, scene, tracker)
    return {
        "oty0_available": oty0 is not None,
        "oty1_available": oty1 is not None,
        "oty1a_available": oty1a is not None,
        "oty1t_available": oty1t is not None,
        "oty0_path": "" if oty0 is None else str(oty0),
        "oty1_path": "" if oty1 is None else str(oty1),
        "oty1a_path": "" if oty1a is None else str(oty1a),
        "oty1t_path": "" if oty1t is None else str(oty1t),
    }


def load_scene_config(path: str | Path) -> dict[str, Any]:
    resolved = resolve_path(path)
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def p4g_scenes(object_rows: Sequence[Mapping[str, Any]], summary: Mapping[str, Any]) -> list[str]:
    scenes = [str(row.get("scene", "") or "") for row in object_rows]
    for row in summary.get("per_scene", []):
        if isinstance(row, Mapping):
            scenes.append(str(row.get("scene", "") or ""))
    return sorted(unique_ordered(scenes))


def select_scenes(args: argparse.Namespace, p4g_scene_names: Sequence[str]) -> list[str]:
    if args.all_available_scenes:
        return list(p4g_scene_names)
    return [args.scene]


def filter_rows_by_scene(rows: Sequence[Mapping[str, Any]], scenes: Sequence[str]) -> list[dict[str, Any]]:
    wanted = set(scenes)
    return [dict(row) for row in rows if str(row.get("scene", "") or "") in wanted]


def write_report_artifacts(
    *,
    timestamp: str,
    summary: Mapping[str, Any],
    scene_status_rows: Sequence[Mapping[str, Any]],
    gating_rows: Sequence[Mapping[str, Any]],
    frame_map_rows: Sequence[Mapping[str, Any]],
    window_rows: Sequence[Mapping[str, Any]],
    uncertainty_report: str,
    overview_svg: Path,
    max_sample_rows: int,
) -> dict[str, str]:
    report_dir = REPO_ROOT / "reports" / "oty2"
    sample_dir = report_dir / "samples"
    viz_dir = sample_dir / "visualizations"
    report_dir.mkdir(parents=True, exist_ok=True)
    sample_dir.mkdir(parents=True, exist_ok=True)
    viz_dir.mkdir(parents=True, exist_ok=True)

    summary_md = report_dir / f"oty2_object_temporal_alignment_summary_{timestamp}.md"
    summary_json = report_dir / f"oty2_object_temporal_alignment_summary_{timestamp}.json"
    summary_md.write_text(render_temporal_alignment_summary_markdown(summary), encoding="utf-8")
    write_json(summary_json, summary)

    scene_sample = sample_dir / "oty2_scene_input_status_sample.csv"
    gating_sample = sample_dir / "oty2_object_readiness_gating_sample.csv"
    frame_map_sample = sample_dir / "oty2_object_alignment_frame_map_sample.csv"
    window_sample = sample_dir / "oty2_object_alignment_window_candidates_sample.csv"
    uncertainty_sample = sample_dir / "oty2_object_alignment_uncertainty_report.md"
    overview_sample = viz_dir / "oty2_object_temporal_alignment_overview.svg"

    write_csv(scene_sample, scene_status_rows, SCENE_INPUT_STATUS_FIELDS)
    write_csv(gating_sample, sample_gating_rows(gating_rows, max_sample_rows), OBJECT_READINESS_GATING_FIELDS)
    write_csv(frame_map_sample, sample_frame_map_rows(frame_map_rows, max_sample_rows), OBJECT_ALIGNMENT_FRAME_MAP_FIELDS)
    write_csv(window_sample, sample_window_rows(window_rows, max_sample_rows), OBJECT_ALIGNMENT_WINDOW_CANDIDATE_FIELDS)
    uncertainty_sample.write_text(uncertainty_report, encoding="utf-8")
    if overview_svg.exists():
        overview_sample.write_text(overview_svg.read_text(encoding="utf-8"), encoding="utf-8")

    return {
        "summary_md": str(summary_md),
        "summary_json": str(summary_json),
        "scene_input_status_sample": str(scene_sample),
        "object_readiness_gating_sample": str(gating_sample),
        "object_alignment_frame_map_sample": str(frame_map_sample),
        "object_alignment_window_candidates_sample": str(window_sample),
        "object_alignment_uncertainty_report_sample": str(uncertainty_sample),
        "object_temporal_alignment_overview_svg": str(overview_sample),
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    timestamp = args.timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    output_root = resolve_path(args.output_root)
    p4g_dir = resolve_path(args.p4g_output_dir) if args.p4g_output_dir else latest_p4g_output_dir(output_root)
    if p4g_dir is None:
        raise FileNotFoundError("Missing OTY1t-P4G output directory under output root.")

    p4g_summary = read_json(p4g_dir / P4G_SUMMARY_FILE)
    p4g_object_rows = read_csv_rows(p4g_dir / P4G_OBJECT_FILE)
    p4g_frame_rows = read_csv_rows(p4g_dir / P4G_FRAME_FILE)
    p4g_orphan_rows = read_csv_rows(p4g_dir / P4G_ORPHAN_FILE) if (p4g_dir / P4G_ORPHAN_FILE).exists() else []
    p4g_scene_names = p4g_scenes(p4g_object_rows, p4g_summary)
    scenes_attempted = select_scenes(args, p4g_scene_names)
    status_scenes = unique_ordered([*scenes_attempted, *p4g_scene_names, "GM_RM011"])
    scene_config = load_scene_config(args.scene_config)
    stage_by_scene = {
        scene: stage_availability(output_root, scene, args.tracker)
        for scene in status_scenes
    }
    scene_status_rows = build_scene_input_status_rows(
        scenes=status_scenes,
        p4g_object_rows=p4g_object_rows,
        p4g_frame_rows=p4g_frame_rows,
        stage_availability_by_scene=stage_by_scene,
        scene_config=scene_config,
    )

    object_rows = filter_rows_by_scene(p4g_object_rows, scenes_attempted)
    frame_rows = filter_rows_by_scene(p4g_frame_rows, scenes_attempted)
    orphan_rows = filter_rows_by_scene(p4g_orphan_rows, scenes_attempted)
    gating_rows = build_object_readiness_gating_rows(object_rows=object_rows, orphan_rows=orphan_rows)
    frame_map_rows = build_object_alignment_frame_map_rows(
        frame_rows=frame_rows,
        gating_rows=gating_rows,
        scene_status_rows=scene_status_rows,
    )
    window_rows = build_object_alignment_window_candidate_rows(
        gating_rows=gating_rows,
        frame_map_rows=frame_map_rows,
    )

    output_dir = output_root / f"oty2_object_temporal_alignment_audit_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now().isoformat(timespec="seconds")
    summary = build_temporal_alignment_summary(
        generated_at=generated_at,
        timestamp=timestamp,
        tracker_name=args.tracker,
        scenes_attempted=scenes_attempted,
        scene_status_rows=scene_status_rows,
        object_rows=object_rows,
        frame_rows=frame_rows,
        gating_rows=gating_rows,
        frame_map_rows=frame_map_rows,
        window_rows=window_rows,
        output_dir=str(output_dir),
    )
    summary["p4g_output_dir"] = str(p4g_dir)
    summary["stage_paths_by_scene"] = stage_by_scene

    uncertainty_report = render_uncertainty_report(
        scene_status_rows=scene_status_rows,
        gating_rows=gating_rows,
        frame_map_rows=frame_map_rows,
        window_rows=window_rows,
        summary=summary,
    )
    overview_svg = output_dir / "visualizations" / "oty2_object_temporal_alignment_overview.svg"
    render_overview_svg(overview_svg, summary)

    write_csv(output_dir / "oty2_scene_input_status.csv", scene_status_rows, SCENE_INPUT_STATUS_FIELDS)
    write_csv(output_dir / "oty2_object_readiness_gating.csv", gating_rows, OBJECT_READINESS_GATING_FIELDS)
    write_csv(output_dir / "oty2_object_alignment_frame_map.csv", frame_map_rows, OBJECT_ALIGNMENT_FRAME_MAP_FIELDS)
    write_csv(
        output_dir / "oty2_object_alignment_window_candidates.csv",
        window_rows,
        OBJECT_ALIGNMENT_WINDOW_CANDIDATE_FIELDS,
    )
    (output_dir / "oty2_object_alignment_uncertainty_report.md").write_text(uncertainty_report, encoding="utf-8")

    summary["artifacts"] = {
        "scene_input_status": str(output_dir / "oty2_scene_input_status.csv"),
        "object_readiness_gating": str(output_dir / "oty2_object_readiness_gating.csv"),
        "object_alignment_frame_map": str(output_dir / "oty2_object_alignment_frame_map.csv"),
        "object_alignment_window_candidates": str(output_dir / "oty2_object_alignment_window_candidates.csv"),
        "object_alignment_uncertainty_report": str(output_dir / "oty2_object_alignment_uncertainty_report.md"),
        "object_temporal_alignment_overview_svg": str(overview_svg),
    }
    write_json(output_dir / "oty2_object_temporal_alignment_summary.json", summary)
    (output_dir / "oty2_object_temporal_alignment_summary.md").write_text(
        render_temporal_alignment_summary_markdown(summary),
        encoding="utf-8",
    )

    report_artifacts = write_report_artifacts(
        timestamp=timestamp,
        summary=summary,
        scene_status_rows=scene_status_rows,
        gating_rows=gating_rows,
        frame_map_rows=frame_map_rows,
        window_rows=window_rows,
        uncertainty_report=uncertainty_report,
        overview_svg=overview_svg,
        max_sample_rows=args.max_sample_rows,
    )
    summary["artifacts"].update(report_artifacts)
    write_json(output_dir / "oty2_object_temporal_alignment_summary.json", summary)
    (output_dir / "oty2_object_temporal_alignment_summary.md").write_text(
        render_temporal_alignment_summary_markdown(summary),
        encoding="utf-8",
    )
    write_json(REPO_ROOT / "reports" / "oty2" / f"oty2_object_temporal_alignment_summary_{timestamp}.json", summary)
    (REPO_ROOT / "reports" / "oty2" / f"oty2_object_temporal_alignment_summary_{timestamp}.md").write_text(
        render_temporal_alignment_summary_markdown(summary),
        encoding="utf-8",
    )
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", default="GM_RM019")
    parser.add_argument("--tracker", default="bytetrack")
    parser.add_argument("--output-root", default="outputs")
    parser.add_argument("--p4g-output-dir", default="")
    parser.add_argument("--scene-config", default="configs/scene_config.yaml")
    parser.add_argument("--timestamp", default="")
    parser.add_argument("--max-sample-rows", type=int, default=120)
    parser.add_argument("--all-available-scenes", action="store_true")
    return parser


def main() -> None:
    summary = run(build_parser().parse_args())
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
