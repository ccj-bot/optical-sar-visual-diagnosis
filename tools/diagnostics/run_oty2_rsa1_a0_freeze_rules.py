from __future__ import annotations

import hashlib
from pathlib import Path

from oty2_rsa1_a0_common import CONFIG_PATH, REPO, RULE_FREEZE_MANIFEST, load_config, sha256_file, write_csv


RULE_SOURCES = [
    CONFIG_PATH,
    REPO / "tools" / "diagnostics" / "oty2_rsa1_a0_common.py",
    REPO / "tools" / "diagnostics" / "run_oty2_rsa1_a0_build_structure_primitives.py",
    REPO / "tools" / "diagnostics" / "run_oty2_rsa1_a0_single_frame_seed_extension.py",
    REPO / "tools" / "diagnostics" / "run_oty2_rsa1_a0_temporal_object_extension.py",
    REPO / "tools" / "diagnostics" / "run_oty2_rsa1_a0_replay_pv003.py",
]


def main() -> None:
    config = load_config()
    development_summary = Path(config["output_root"]) / "development" / "pv002_temporal" / "summary.json"
    hidden_freeze = REPO / "manifests" / "oty2" / "oty2_rsa1_a0_hidden_reference_freeze_manifest.csv"
    for path in [*RULE_SOURCES, development_summary, hidden_freeze]:
        if not path.is_file():
            raise FileNotFoundError(path)
    forbidden_replay = Path(config["output_root"]) / "frozen_replay" / "pv003_gt"
    if forbidden_replay.exists():
        raise RuntimeError("PV003 propagation output already exists before rule freeze")

    source_hashes = [(path, sha256_file(path)) for path in RULE_SOURCES]
    aggregate_text = "\n".join(
        sorted(f"{path.relative_to(REPO).as_posix()}:{digest}" for path, digest in source_hashes)
    )
    aggregate_sha = hashlib.sha256(aggregate_text.encode("utf-8")).hexdigest()
    fields = [
        "freeze_version",
        "entry_role",
        "path",
        "sha256",
        "size_bytes",
        "aggregate_rule_sha256",
        "notes",
    ]
    rows = []
    for path, digest in source_hashes:
        rows.append(
            {
                "freeze_version": "OTY2-RSA1-A0-rule-freeze-v1",
                "entry_role": "frozen_rule_source",
                "path": path.relative_to(REPO).as_posix(),
                "sha256": digest,
                "size_bytes": path.stat().st_size,
                "aggregate_rule_sha256": aggregate_sha,
                "notes": "must remain byte-identical before and during PV003 replay",
            }
        )
    for role, path in [
        ("pv002_development_evidence", development_summary),
        ("hidden_reference_freeze_precondition", hidden_freeze),
    ]:
        rows.append(
            {
                "freeze_version": "OTY2-RSA1-A0-rule-freeze-v1",
                "entry_role": role,
                "path": str(path),
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
                "aggregate_rule_sha256": aggregate_sha,
                "notes": "evidence/precondition binding; not a propagation rule source",
            }
        )
    write_csv(RULE_FREEZE_MANIFEST, rows, fields)
    print(f"rule_freeze_sha256={aggregate_sha}")
    print(f"rule_freeze_manifest={RULE_FREEZE_MANIFEST}")


if __name__ == "__main__":
    main()
