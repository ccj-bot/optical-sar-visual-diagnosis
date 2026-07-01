"""Manifest and accounting-table helpers for V0 visual diagnostics."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Iterable

from .config import accounting_path_for, source_metadata_for


CANDIDATE_LOADING_REPORT_FIELDS = [
    "sample_id",
    "scene",
    "target_identity",
    "sample_type",
    "requested_source_id",
    "resolved_source_path",
    "source_kind",
    "source_exists",
    "exact_match_count",
    "fallback_used",
    "fallback_reason",
    "fallback_row_count",
    "first_target_used_if_fallback",
    "candidate_count",
    "missing_candidate_geometry_count",
    "missing_rank_count",
    "missing_candidate_source_family_count",
    "missing_factor_fields",
    "notes",
]


MISSING_FIELD_REPORT_FIELDS = [
    "sample_id",
    "source_id",
    "source_kind",
    "field",
    "missing_count",
    "candidate_count",
    "context",
]


FACTOR_FIELD_GROUPS = {
    "prior_delta": ("delta_r_from_pred", "delta_az_from_pred", "delta_cross_from_pred"),
    "wedge_support": ("wedge_support_type", "wedge_mode_rank", "wedge_posterior_score", "directional_shell_score"),
    "ray_support": ("ray_support_type", "ray_mode_rank", "ray_sar_peak_score", "ray_track_score"),
    "signed_temporal_support": (
        "signed_direction_match_tracklet_refined",
        "signed_direction_match_refined",
        "signed_direction_match",
        "signed_escape_direction",
    ),
    "visible_risk": (
        "visible_risk",
        "sar_support_leakage_status",
        "sar_local_background_contrast_status",
        "sar_body_compactness_status",
    ),
    "conflict_score": ("escape_conflict_score", "posterior_margin", "posterior_margin_refined"),
}


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
    source_id = completed.get("source_id") or completed.get("accounting_source", "")
    source_meta = source_metadata_for(config, source_id)
    if source_id and not completed.get("source_id"):
        completed["source_id"] = source_id
    if source_meta and not completed.get("source_kind"):
        completed["source_kind"] = str(source_meta.get("source_kind", ""))
    frame_num = parse_int(completed.get("sar_frame_num"))
    if frame_num is not None:
        frame_name = f"{frame_num:06d}.png"
        if not completed.get("sar_frame_path") and paths.get("sar_frames_dir"):
            completed["sar_frame_path"] = str(Path(paths["sar_frames_dir"]) / frame_name)
        if (
            not completed.get("optical_frame_path")
            and paths.get("optical_frames_dir")
            and not truthy(completed.get("no_optical_runtime_prior"))
            and "sar_only" not in completed.get("sample_type", "").lower()
        ):
            completed["optical_frame_path"] = str(Path(paths["optical_frames_dir"]) / frame_name)
    accounting_source = completed.get("accounting_source", "")
    if not completed.get("candidate_accounting_csv") and source_id:
        completed["candidate_accounting_csv"] = accounting_path_for(config, scene, source_id)
    elif not completed.get("candidate_accounting_csv") and accounting_source:
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
    candidates, _ = load_candidates_with_report(sample)
    return candidates


def load_candidates_with_report(sample: dict[str, str]) -> tuple[list[dict[str, str]], dict[str, Any]]:
    path = sample.get("candidate_accounting_csv", "").strip()
    source_id = sample.get("source_id") or sample.get("accounting_source", "")
    source_kind = sample.get("source_kind", "")
    base_report: dict[str, Any] = {
        "sample_id": sample.get("sample_id", ""),
        "scene": sample.get("scene", ""),
        "target_identity": sample.get("target_identity", ""),
        "sample_type": sample.get("sample_type", ""),
        "requested_source_id": source_id,
        "resolved_source_path": path,
        "source_kind": source_kind,
        "source_exists": bool(path and Path(path).exists()),
        "exact_match_count": 0,
        "fallback_used": False,
        "fallback_reason": "",
        "fallback_row_count": 0,
        "first_target_used_if_fallback": "",
        "candidate_count": 0,
        "missing_candidate_geometry_count": 0,
        "missing_rank_count": 0,
        "missing_candidate_source_family_count": 0,
        "missing_factor_fields": "",
        "notes": "",
    }
    if not path or not Path(path).exists():
        base_report["fallback_reason"] = "no_source_path" if not path else "source_path_not_found"
        base_report["notes"] = "No candidate rows loaded; missing source is explicit."
        return [], base_report
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
    base_report["exact_match_count"] = len(filtered)
    if filtered:
        _fill_candidate_report(base_report, filtered)
        return filtered, base_report
    fallback = sample_from_accounting(rows, sample)
    base_report["fallback_used"] = bool(fallback)
    base_report["fallback_reason"] = "no_exact_scene_target_or_frame_match"
    base_report["fallback_row_count"] = len(fallback)
    base_report["first_target_used_if_fallback"] = fallback[0].get("target_identity", "") if fallback else ""
    base_report["notes"] = "Fallback rows are visible in reports; they are not silent runtime evidence."
    _fill_candidate_report(base_report, fallback)
    return fallback, base_report


def _has_any(row: dict[str, str], keys: tuple[str, ...]) -> bool:
    return any(str(row.get(key, "")).strip() for key in keys)


def _missing_geometry(row: dict[str, str]) -> bool:
    return not all(parse_float(row.get(key, "")) is not None for key in ("cx", "cy", "w", "h"))


def _missing_rank(row: dict[str, str]) -> bool:
    return not _has_any(row, ("rank", "candidate_rank", "frozen_rank", "pilot_rank", "c1_2_mode_rank"))


def _missing_source_family(row: dict[str, str]) -> bool:
    return not _has_any(row, ("candidate_source_family", "candidate_source"))


def _missing_factor_group(rows: list[dict[str, str]], keys: tuple[str, ...]) -> bool:
    if not rows:
        return True
    return not any(_has_any(row, keys) for row in rows)


def _fill_candidate_report(report: dict[str, Any], candidates: list[dict[str, str]]) -> None:
    report["candidate_count"] = len(candidates)
    report["missing_candidate_geometry_count"] = sum(1 for row in candidates if _missing_geometry(row))
    report["missing_rank_count"] = sum(1 for row in candidates if _missing_rank(row))
    report["missing_candidate_source_family_count"] = sum(1 for row in candidates if _missing_source_family(row))
    missing_groups = [
        name for name, keys in FACTOR_FIELD_GROUPS.items() if _missing_factor_group(candidates, keys)
    ]
    report["missing_factor_fields"] = ";".join(missing_groups)


def collect_missing_candidate_fields(
    samples: Iterable[dict[str, str]],
    candidates_by_sample: dict[str, list[dict[str, str]]],
) -> list[dict[str, Any]]:
    missing: list[dict[str, Any]] = []
    for sample in samples:
        sample_id = sample.get("sample_id", "")
        source_id = sample.get("source_id", "")
        source_kind = sample.get("source_kind", "")
        rows = candidates_by_sample.get(sample_id, [])
        count = len(rows)
        if not rows:
            missing.append(
                {
                    "sample_id": sample_id,
                    "source_id": source_id,
                    "source_kind": source_kind,
                    "field": "candidate_rows",
                    "missing_count": 1,
                    "candidate_count": 0,
                    "context": "no candidates loaded for sample",
                }
            )
            continue
        checks = {
            "candidate_geometry": lambda row: _missing_geometry(row),
            "rank_or_frozen_rank": lambda row: _missing_rank(row),
            "candidate_source_family": lambda row: _missing_source_family(row),
        }
        for field, checker in checks.items():
            missing_count = sum(1 for row in rows if checker(row))
            if missing_count:
                missing.append(
                    {
                        "sample_id": sample_id,
                        "source_id": source_id,
                        "source_kind": source_kind,
                        "field": field,
                        "missing_count": missing_count,
                        "candidate_count": count,
                        "context": "candidate-level field",
                    }
                )
        for group, keys in FACTOR_FIELD_GROUPS.items():
            if _missing_factor_group(rows, keys):
                missing.append(
                    {
                        "sample_id": sample_id,
                        "source_id": source_id,
                        "source_kind": source_kind,
                        "field": group,
                        "missing_count": count,
                        "candidate_count": count,
                        "context": "factor group absent from all loaded rows",
                    }
                )
    return missing


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
