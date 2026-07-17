from __future__ import annotations

import json
from pathlib import Path

from oty2_rsa1_a0_common import (
    PRIMITIVE_FIELDS,
    TRACE_FIELDS,
    REPO,
    load_config,
    read_csv,
    run_temporal_case,
    verify_rule_freeze,
    write_csv,
)


FINAL_PRIMITIVES = REPO / "manifests" / "oty2" / "oty2_rsa1_a0_structure_primitives.csv"
FINAL_TRACE = REPO / "manifests" / "oty2" / "oty2_rsa1_a0_expansion_trace.csv"


def collect_stage(directory: Path) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    primitives = read_csv(directory / "spatial_structure_primitives.csv") + read_csv(
        directory / "temporal_structure_primitives.csv"
    )
    traces = read_csv(directory / "spatial_expansion_trace.csv") + read_csv(directory / "temporal_expansion_trace.csv")
    return primitives, traces


def main() -> None:
    rule_sha = verify_rule_freeze()
    config = load_config()
    output_root = Path(config["output_root"])
    pv002_gt = output_root / "development" / "pv002_temporal"
    for required in (
        pv002_gt / "spatial_structure_primitives.csv",
        pv002_gt / "spatial_expansion_trace.csv",
        pv002_gt / "temporal_structure_primitives.csv",
        pv002_gt / "temporal_expansion_trace.csv",
    ):
        if not required.is_file():
            raise FileNotFoundError(required)

    replay_root = output_root / "frozen_replay"
    pv003_gt = replay_root / "pv003_gt"
    run_temporal_case(
        "PV003_380_384",
        config["primary_coordinate_family"],
        pv003_gt,
        render_cards=True,
    )

    # Sensitivity runs occur only after the same rule hash is frozen. They are
    # never used to modify thresholds or the primary GT-aligned conclusion.
    pv002_proxy = replay_root / "pv002_proxy_sensitivity"
    run_temporal_case(
        "PV002_337_341",
        config["sensitivity_coordinate_family"],
        pv002_proxy,
        render_cards=True,
    )
    pv003_proxy = replay_root / "pv003_proxy_sensitivity"
    run_temporal_case(
        "PV003_380_384",
        config["sensitivity_coordinate_family"],
        pv003_proxy,
        render_cards=True,
    )

    primitive_rows: list[dict[str, str]] = []
    trace_rows: list[dict[str, str]] = []
    for directory in (pv002_gt, pv003_gt, pv002_proxy, pv003_proxy):
        stage_primitives, stage_trace = collect_stage(directory)
        primitive_rows.extend(stage_primitives)
        trace_rows.extend(stage_trace)
    write_csv(FINAL_PRIMITIVES, primitive_rows, PRIMITIVE_FIELDS)
    write_csv(FINAL_TRACE, trace_rows, TRACE_FIELDS)

    state_counts: dict[str, int] = {}
    for row in primitive_rows:
        key = f"{row['case_id']}:{row['coordinate_family']}:{row['propagation_mode']}:{row['state']}"
        state_counts[key] = state_counts.get(key, 0) + 1
    summary = {
        "rule_freeze_sha256": rule_sha,
        "primitive_count": len(primitive_rows),
        "trace_count": len(trace_rows),
        "state_counts": state_counts,
        "final_primitives": str(FINAL_PRIMITIVES),
        "final_trace": str(FINAL_TRACE),
        "pv003_tuning_performed": False,
    }
    summary_path = replay_root / "replay_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"summary={summary_path}")


if __name__ == "__main__":
    main()
