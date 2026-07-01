"""Manifest and accounting-table helpers for V0 visual diagnostics."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Iterable

from .config import accounting_path_for


def read_csv_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def load_manifest(path: str | Path, config: dict[str, Any]) -> list[dict[str, str]]:
    rows = read_csv_rows(path)
    return [complete_manifest_row(row, config) for row in rows]


def complete_manifest_row(row: dict[str, str], config: dict[str, Any]) -> dict[str, str]:
    completed = dict(row)
    scene = completed.get("scene", "")
    scene_cfg = config.get("scenes", {}).get(scene, {})
    paths = scene_cfg.get("paths", {})
    frame_num = parse_int(completed.get("sar_frame_num"))
    if frame_num is not None:
        frame_name = f"{frame_num:06d}.png"
        if not completed.get("sar_frame_path") and paths.get("sar_frames_dir"):
            completed["sar_frame_path"] = str(Path(paths["sar_frames_dir"]) / frame_name)
        if not completed.get("optical_frame_path") and paths.get("optical_frames_dir"):
            completed["optical_frame_path"] = str(Path(paths["optical_frames_dir"]) / frame_name)
    accounting_source = completed.get("accounting_source", "")
    if not completed.get("candidate_accounting_csv") and accounting_source:
        completed["candidate_accounting_csv"] = accounting_path_for(config, scene, accounting_source)
    if not completed.get("sample_id"):
        completed["sample_id"] = f"{scene}_{frame_num or 0:06d}"
    return completed


def parse_int(value: Any) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def parse_float(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_xywh(value: str) -> tuple[float, float, float, float] | None:
    text = str(value or "").strip()
    if not text:
        return None
    parts = [part.strip() for part in text.replace(";", ",").split(",")]
    if len(parts) != 4:
        return None
    try:
        return tuple(float(part) for part in parts)  # type: ignore[return-value]
    except ValueError:
        return None


def load_candidates_for_sample(sample: dict[str, str]) -> list[dict[str, str]]:
    path = sample.get("candidate_accounting_csv", "").strip()
    if not path or not Path(path).exists():
        return []
    rows = read_csv_rows(path)
    scene = sample.get("scene", "")
    target = sample.get("target_identity", "")
    frame_num = sample.get("sar_frame_num", "")
    filtered: list[dict[str, str]] = []
    for index, row in enumerate(rows, start=1):
        if scene and row.get("scene") and row.get("scene") != scene:
            continue
        if target and row.get("target_identity") and row.get("target_identity") != target:
            continue
        if not target and frame_num and str(row.get("sar_frame_num", "")) != str(frame_num):
            continue
        enriched = dict(row)
        enriched["_row_index"] = str(index)
        filtered.append(enriched)
    if filtered:
        return filtered
    return sample_from_accounting(rows, sample)


def sample_from_accounting(
    rows: list[dict[str, str]],
    sample: dict[str, str],
    limit: int = 24,
) -> list[dict[str, str]]:
    """Fallback sampler for manually sparse rows.

    This supports the first V0 pass where the manifest may name only a scene,
    sample type, and old C1.3/C1.4 accounting source.
    """

    scene = sample.get("scene", "")
    source_hint = sample.get("sample_type", "").lower().replace(" ", "_")
    out: list[dict[str, str]] = []
    first_target = ""
    for index, row in enumerate(rows, start=1):
        if scene and row.get("scene") and row.get("scene") != scene:
            continue
        text = " ".join(
            str(row.get(key, "")).lower()
            for key in ("candidate_source", "candidate_source_family", "candidate_detail", "c1_2_mode_type")
        )
        if any(token in source_hint for token in ("wedge", "ray", "signed")):
            token = "signed" if "signed" in source_hint else ("wedge" if "wedge" in source_hint else "ray")
            if token not in text:
                continue
        if not first_target:
            first_target = row.get("target_identity", "")
        if first_target and row.get("target_identity") != first_target:
            continue
        enriched = dict(row)
        enriched["_row_index"] = str(index)
        out.append(enriched)
        if len(out) >= limit:
            break
    return out


def collect_missing_paths(
    samples: Iterable[dict[str, str]],
    extra_paths: Iterable[tuple[str, str, str]] = (),
) -> list[dict[str, str]]:
    missing: list[dict[str, str]] = []
    for sample in samples:
        sample_id = sample.get("sample_id", "")
        for kind, field in (
            ("optical_frame", "optical_frame_path"),
            ("sar_frame", "sar_frame_path"),
            ("candidate_accounting_csv", "candidate_accounting_csv"),
        ):
            value = sample.get(field, "").strip()
            if field == "candidate_accounting_csv" and not value:
                continue
            if not value:
                missing.append(
                    {"sample_id": sample_id, "kind": kind, "path": "", "reason": "empty_path"}
                )
            elif not Path(value).exists():
                missing.append(
                    {"sample_id": sample_id, "kind": kind, "path": value, "reason": "path_not_found"}
                )
    for sample_id, kind, value in extra_paths:
        if not value:
            missing.append({"sample_id": sample_id, "kind": kind, "path": "", "reason": "empty_path"})
        elif not Path(value).exists():
            missing.append({"sample_id": sample_id, "kind": kind, "path": value, "reason": "path_not_found"})
    return missing


def write_csv(path: str | Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with Path(path).open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
