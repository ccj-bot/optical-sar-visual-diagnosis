from __future__ import annotations

import json
from pathlib import Path

from oty2_rsa1_a0_common import load_config, run_case_frames, summarize_stage


def main() -> None:
    config = load_config()
    output = Path(config["output_root"]) / "development" / "pv002_primary_primitives"
    primitive_path, trace_path = run_case_frames(
        "PV002_337_341",
        config["primary_coordinate_family"],
        [339],
        output,
        render_cards=False,
    )
    summary = summarize_stage(primitive_path, trace_path)
    summary_path = output / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"summary={summary_path}")


if __name__ == "__main__":
    main()
