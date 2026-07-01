"""Input-source registry helpers for visual diagnosis runs."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable


REGISTRY_FIELDS = [
    "source_id",
    "scene",
    "stage",
    "source_path",
    "source_exists",
    "source_origin",
    "source_kind",
    "row_count",
    "target_count",
    "has_candidate_geometry",
    "has_rank",
    "has_frozen_rank",
    "has_candidate_source_family",
    "has_wedge_ray_signed",
    "has_temporal_fields",
    "has_posthoc_iou",
    "allowed_use",
    "forbidden_use",
    "lineage_notes",
]


def _read_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        return list(reader.fieldnames or []), rows


def _any_field(columns: Iterable[str], needles: tuple[str, ...]) -> bool:
    lowered = [column.lower() for column in columns]
    return any(any(needle in column for needle in needles) for column in lowered)


def _any_value(rows: list[dict[str, str]], keys: tuple[str, ...], needles: tuple[str, ...]) -> bool:
    for row in rows:
        text = " ".join(str(row.get(key, "")).lower() for key in keys)
        if any(needle in text for needle in needles):
            return True
    return False


def inspect_input_source(source_id: str, raw: dict[str, Any]) -> dict[str, Any]:
    source_path = str(raw.get("source_path", "") or "")
    path = Path(source_path) if source_path else None
    exists = bool(path and path.exists())
    columns: list[str] = []
    rows: list[dict[str, str]] = []
    if exists and path and path.suffix.lower() == ".csv":
        columns, rows = _read_csv_rows(path)

    has_geometry = all(name in columns for name in ("cx", "cy", "w", "h")) or "candidate_geometry_display_xy" in columns
    has_rank = any(name in columns for name in ("rank", "candidate_rank", "pilot_rank"))
    has_frozen_rank = any(name in columns for name in ("frozen_rank", "rank_group", "rank_policy_version"))
    has_family = "candidate_source_family" in columns
    has_structural = _any_field(columns, ("wedge", "ray", "signed", "tracklet")) or _any_value(
        rows,
        ("candidate_source", "candidate_source_family", "candidate_detail"),
        ("wedge", "ray", "signed", "track"),
    )
    has_temporal = _any_field(columns, ("temporal", "tracklet", "neighbor", "signed")) or _any_value(
        rows,
        ("candidate_source", "candidate_source_family", "candidate_detail"),
        ("signed", "track"),
    )
    has_posthoc = _any_field(
        columns,
        ("iou", "oracle", "final_box", "posthoc_iou", "posthoc_aabb", "axis_aligned_proxy_iou"),
    )
    targets = {row.get("target_identity", "") for row in rows if row.get("target_identity", "")}

    return {
        "source_id": source_id,
        "scene": str(raw.get("scene", "")),
        "stage": str(raw.get("stage", "")),
        "source_path": source_path,
        "source_exists": exists,
        "source_origin": str(raw.get("source_origin", "")),
        "source_kind": str(raw.get("source_kind", "")),
        "row_count": len(rows),
        "target_count": len(targets),
        "has_candidate_geometry": has_geometry,
        "has_rank": has_rank,
        "has_frozen_rank": has_frozen_rank,
        "has_candidate_source_family": has_family,
        "has_wedge_ray_signed": has_structural,
        "has_temporal_fields": has_temporal,
        "has_posthoc_iou": has_posthoc,
        "allowed_use": str(raw.get("allowed_use", "")),
        "forbidden_use": str(raw.get("forbidden_use", "")),
        "lineage_notes": str(raw.get("lineage_notes", "")),
    }


def build_input_source_registry(config: dict[str, Any]) -> list[dict[str, Any]]:
    sources = config.get("input_sources", {})
    return [inspect_input_source(source_id, raw) for source_id, raw in sources.items()]


def source_by_id(registry: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(item.get("source_id", "")): item for item in registry}


def write_registry_json(path: str | Path, registry: list[dict[str, Any]]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")


def write_registry_markdown(path: str | Path, registry: list[dict[str, Any]]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# V0.1 Input Source Registry",
        "",
        "This registry separates runtime candidate banks, frozen ranked candidates, partial factor audits, posthoc accounting, and manual probe rows. Posthoc/final/oracle/GT fields remain diagnostic-only and cannot enter runtime generation or ranking.",
        "",
        "| source_id | scene | stage | origin | kind | exists | rows | targets | geometry | rank | frozen_rank | family | wedge/ray/signed | temporal | posthoc_iou | allowed_use | forbidden_use |",
        "|---|---|---|---|---|---:|---:|---:|---|---|---|---|---|---|---|---|---|",
    ]
    for item in registry:
        lines.append(
            "| {source_id} | {scene} | {stage} | {source_origin} | {source_kind} | {source_exists} | {row_count} | {target_count} | {has_candidate_geometry} | {has_rank} | {has_frozen_rank} | {has_candidate_source_family} | {has_wedge_ray_signed} | {has_temporal_fields} | {has_posthoc_iou} | {allowed_use} | {forbidden_use} |".format(
                **{key: str(item.get(key, "")) for key in REGISTRY_FIELDS}
            )
        )
    lines.extend(
        [
            "",
            "## Lineage Notes",
            "",
        ]
    )
    for item in registry:
        lines.append(f"- `{item.get('source_id', '')}`: {item.get('lineage_notes', '')}")
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
