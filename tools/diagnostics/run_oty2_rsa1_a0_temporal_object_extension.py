from __future__ import annotations

import json
from pathlib import Path

from oty2_rsa1_a0_common import load_config, read_csv, run_temporal_case


def count_states(path: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in read_csv(path):
        key = f"{row['propagation_mode']}:{row['state']}"
        counts[key] = counts.get(key, 0) + 1
    return counts


def main() -> None:
    config = load_config()
    output = Path(config["output_root"]) / "development" / "pv002_temporal"
    spatial_primitives, spatial_trace, temporal_primitives, temporal_trace = run_temporal_case(
        "PV002_337_341",
        config["primary_coordinate_family"],
        output,
        render_cards=True,
    )
    summary = {
        "spatial_primitive_count": len(read_csv(spatial_primitives)),
        "spatial_trace_count": len(read_csv(spatial_trace)),
        "temporal_primitive_count": len(read_csv(temporal_primitives)),
        "temporal_trace_count": len(read_csv(temporal_trace)),
        "temporal_state_counts": count_states(temporal_primitives),
        "spatial_primitives": str(spatial_primitives),
        "spatial_trace": str(spatial_trace),
        "temporal_primitives": str(temporal_primitives),
        "temporal_trace": str(temporal_trace),
    }
    summary_path = output / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"summary={summary_path}")


if __name__ == "__main__":
    main()
