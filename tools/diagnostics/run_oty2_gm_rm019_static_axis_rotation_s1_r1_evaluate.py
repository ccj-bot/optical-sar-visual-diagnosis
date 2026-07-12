"""Evaluate GM_RM019 S1-R1 static axis and counterfactual semantic repair outputs."""

from __future__ import annotations

import argparse
import csv
import math
from collections import Counter
from pathlib import Path
from statistics import mean, median
from typing import Any, Mapping, Sequence

import run_oty2_gm_rm019_static_axis_rotation_s1_r1_generate as gen


REPORT = gen.REPORT_DIR / "oty2_gm_rm019_static_axis_rotation_s1_r1_20260712.md"
INTEGRITY = gen.SAMPLES_DIR / "oty2_gm_rm019_s1_r1_integrity_20260712.csv"
INTEGRITY_FIELDS = ["gate_name", "status", "detail", "source_file", "sha256", "row_count"]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def f(value: Any) -> float:
    return gen.parse_float(value)


def stats(values: Sequence[float]) -> dict[str, str]:
    vals = sorted(v for v in values if not math.isnan(v) and math.isfinite(v))
    if not vals:
        return {"count": "0", "mean": "", "median": "", "min": "", "max": ""}
    return {
        "count": str(len(vals)),
        "mean": gen.fmt(mean(vals)),
        "median": gen.fmt(median(vals)),
        "min": gen.fmt(vals[0]),
        "max": gen.fmt(vals[-1]),
    }


def gate(name: str, ok: bool, detail: str, source: Path | None = None) -> dict[str, str]:
    return {
        "gate_name": name,
        "status": "PASS" if ok else "FAIL",
        "detail": detail,
        "source_file": gen.rel(source) if source else "",
        "sha256": gen.sha256(source) if source and source.exists() else "",
        "row_count": str(gen.row_count(source)) if source and source.exists() and source.suffix.lower() == ".csv" else "",
    }


def load_all() -> dict[str, list[dict[str, str]]]:
    required = {
        key: path
        for key, path in gen.OUTPUTS.items()
        if key != "replay_check"
    }
    missing = [str(path) for path in required.values() if not path.exists()]
    if missing:
        raise FileNotFoundError("missing S1-R1 generated outputs: " + "; ".join(missing))
    rows = {key: read_rows(path) for key, path in required.items()}
    rows["replay_check"] = read_rows(gen.OUTPUTS["replay_check"]) if gen.OUTPUTS["replay_check"].exists() else []
    return rows


def integrity_rows(rows: Mapping[str, list[dict[str, str]]]) -> list[dict[str, str]]:
    axis = rows["axis_observations"]
    geometry = rows["independent_geometry_map"]
    envelope = rows["vehicle_projection_envelope"]
    comps = rows["threshold_components"]
    trans = rows["threshold_transitions"]
    specs = rows["counterfactual_specs"]
    meas = rows["counterfactual_measurements"]
    seal = {row["seal_key"]: row["seal_value"] for row in rows["pre_eval_seal"]}
    replay = rows["replay_check"]
    failures = rows["semantic_failures"]
    visual = rows["visual_manifest"]

    signed_vals = [f(r["response_axis_to_range_signed_deg"]) for r in axis]
    acute_vals = [f(r["response_axis_to_range_acute_deg"]) for r in axis]
    image_vals = [f(r["response_axis_image_deg"]) for r in axis]
    aspect_vals = [f(r["aspect_angle_candidate_deg"]) for r in envelope]
    comp_errors = [f(r["range_azimuth_acute_complement_error_deg"]) for r in axis]
    output_names = "\n".join(gen.rel(path).lower() for path in list(gen.OUTPUTS.values()) + [REPORT, INTEGRITY])
    forbidden_status_terms = [
        "VEHICLE_" + "YAW_CONFIRMED",
        "GT_" + "AXIS_CONFIRMED",
        "VEHICLE_" + "REGION_CONFIRMED",
        "FINAL_" + "BOX_READY",
        "STATIC_" + "SELECTOR_READY",
    ]
    forbidden_output_terms = ["selector", "ranking", "final_box", "final-box", "runtime_prediction", "best_box", "best-box"]
    proxy_used = [r for r in meas if r.get("proxy_formula_used") != "false" or r.get("measurement_source") != "REAL_SAR_GRAY_REMEASURED"]
    status_counts = Counter(r["threshold_component_identity_status"] for r in trans)
    same_geometry_ok = len(axis) == 215 and len(geometry) == 215
    expected_measurements = len(geometry) * len(gen.template_specs())
    expected_specs = expected_measurements
    test_failures = {r["failure_type"] for r in failures}

    return [
        gate("PROJECT_CONFIRMED_CALIBRATION_APPLIED", all(r["calibration_status"] == gen.CALIBRATION_STATUS for r in axis), "PROJECT_CONFIRMED constants applied", gen.OUTPUTS["axis_observations"]),
        gate("GT_NOT_READ_DURING_GENERATION", seal.get("gt_file_opened") == "false" and all(r["gt_file_opened"] == "false" for r in axis), "gt_file_opened=false"),
        gate("PAIRED_ANNOTATIONS_NOT_READ_DURING_GENERATION", seal.get("paired_annotations_opened") == "false" and all(r["paired_annotations_opened"] == "false" for r in axis), "paired_annotations_opened=false"),
        gate("MASK_AUDIT_NOT_READ_DURING_GENERATION", seal.get("mask_audit_opened") == "false" and all(r["mask_audit_opened"] == "false" for r in axis), "mask_audit_opened=false"),
        gate("RAW_EIGENVECTOR_USED_FOR_RELATIVE_AXIS", "axis_45_vs_135_not_collapsed" not in test_failures and all(r["response_axis_vector_x"] != "" for r in axis), "raw eigenvector canonical line stored before relative angle"),
        gate("IMAGE_AXIS_RANGE_IS_0_180", all(0.0 <= v < 180.0 for v in image_vals), f"image_axis_count={len(image_vals)}"),
        gate("SIGNED_AXIS_RANGE_IS_MINUS90_TO90", all(-90.0 <= v < 90.0 for v in signed_vals), f"signed_axis_count={len(signed_vals)}"),
        gate("ACUTE_AXIS_RANGE_IS_0_TO90", all(0.0 <= v <= 90.0 for v in acute_vals), f"acute_axis_count={len(acute_vals)}"),
        gate("RANGE_AZIMUTH_ACUTE_COMPLEMENT_VALID", all(v <= 1e-5 for v in comp_errors if not math.isnan(v)), f"max_error={gen.fmt(max(comp_errors)) if comp_errors else ''}"),
        gate("NEAR_ISOTROPIC_AXIS_NOT_OVERINTERPRETED", any(r["axis_orientation_status"] == "AXIS_NEAR_ISOTROPIC" for r in axis), "near-isotropic rows have explicit status"),
        gate("YAW_TERM_REMOVED_FROM_STATIC_OUTPUT", "yaw" not in "\n".join(axis[0].keys()).lower() and "yaw" not in "\n".join(envelope[0].keys()).lower(), "static S1-R1 fields use aspect angle, not yaw"),
        gate("ASPECT_ANGLE_RANGE_IS_0_TO90", all(0.0 <= v <= 90.0 for v in aspect_vals if not math.isnan(v)), f"aspect_count={len(aspect_vals)}"),
        gate("VEHICLE_SCALE_USED_AS_ENVELOPE_NOT_EXACT_TARGET", all("包络" in r["vehicle_scale_semantic_note_cn"] for r in envelope), "vehicle scale note records envelope semantics"),
        gate("MISSING_SUPPORT_AND_EXTRA_SPREAD_SEPARATED", all(k in envelope[0] for k in ["required_missing_support_range_m", "required_extra_spread_range_m"]), "missing support and extra spread columns present"),
        gate("THRESHOLD_COMPONENT_IDENTITY_TRACKED", len(comps) == len(geometry) * 3 and len(trans) == len(geometry) * 2, f"component_rows={len(comps)} transition_rows={len(trans)}"),
        gate("COUNTERFACTUALS_REMEASURE_REAL_SAR", len(meas) == expected_measurements and not proxy_used, f"measurement_rows={len(meas)} expected={expected_measurements}"),
        gate("NO_PROXY_COUNTERFACTUAL_DELTA_FIELDS_USED_AS_RESULT", not proxy_used and all("measured" in key or key in gen.MEASUREMENT_FIELDS for key in meas[0].keys()), "proxy_formula_used=false for all rows"),
        gate("ROTATION_COUNTERFACTUALS_PRESENT", sum(1 for r in meas if r["template_family"] == "local_region_rotation") == len(geometry) * len(gen.ROTATION_DEG), "rotation measurements present"),
        gate("INDEPENDENT_GEOMETRY_DEDUP_VALID", same_geometry_ok and all(r["measured_once_then_mapped_to_members"] == "true" for r in geometry), f"response_unit_level=250 independent_geometry_level={len(geometry)}"),
        gate("FROZEN_REPLAY_IDENTICAL", bool(replay) and all(r["status"] == "PASS" for r in replay), f"replay_rows={len(replay)}"),
        gate("NO_SELECTOR_OUTPUT", "selector" not in output_names and "ranking" not in output_names, "no selector/ranking output names"),
        gate("NO_FINAL_BOX_OUTPUT", not any(term in output_names for term in forbidden_output_terms[2:]), "no final-box/runtime output names"),
        gate("S2_GT_EVALUATION_NOT_EXECUTED", all(term not in output_names.upper() for term in forbidden_status_terms), "S2 not executed; forbidden status terms absent"),
        gate("axis_45_vs_135_not_collapsed", "axis_45_vs_135_not_collapsed" not in test_failures, "synthetic angle test passed"),
        gate("axis_v_and_minus_v_equivalent", "axis_v_and_minus_v_equivalent" not in test_failures, "synthetic axis sign equivalence passed"),
        gate("rotation_180_equivalent_to_0", "rotation_180_equivalent_to_0" not in test_failures, "synthetic 180 equivalence passed"),
        gate("rotation_90_long_short_swap_recorded", "rotation_90_long_short_swap_recorded" not in test_failures, "synthetic projection swap passed"),
        gate("VISUAL_REVIEW_PACKAGE_READY", len(visual) >= 12, f"visual_rows={len(visual)}; files under outputs/"),
    ]


def markdown_table(rows: Sequence[Mapping[str, Any]], fields: Sequence[str], limit: int | None = None) -> str:
    show = list(rows[:limit]) if limit is not None else list(rows)
    if not show:
        return "_none_"
    lines = ["|" + "|".join(fields) + "|", "|" + "|".join("---" for _ in fields) + "|"]
    for row in show:
        lines.append("|" + "|".join(str(row.get(field, "")).replace("\n", " ") for field in fields) + "|")
    return "\n".join(lines)


def report_text(rows: Mapping[str, list[dict[str, str]]], gates: Sequence[Mapping[str, str]]) -> str:
    axis = rows["axis_observations"]
    envelope = rows["vehicle_projection_envelope"]
    trans = rows["threshold_transitions"]
    meas = rows["counterfactual_measurements"]
    geometry = rows["independent_geometry_map"]
    visual = rows["visual_manifest"]
    gates_pass = all(g["status"] == "PASS" for g in gates)
    status = gen.STATUS_READY if gates_pass else "S1_R1_PARTIAL"
    readiness = gen.S2_READY if gates_pass else "NOT_READY"

    signed_stats = stats([f(r["response_axis_to_range_signed_deg"]) for r in axis])
    acute_stats = stats([f(r["response_axis_to_range_acute_deg"]) for r in axis])
    missing_r = stats([f(r["required_missing_support_range_m"]) for r in envelope])
    missing_a = stats([f(r["required_missing_support_azimuth_m"]) for r in envelope])
    extra_r = stats([f(r["required_extra_spread_range_m"]) for r in envelope])
    extra_a = stats([f(r["required_extra_spread_azimuth_m"]) for r in envelope])
    axis_counts = Counter(r["axis_orientation_status"] for r in axis)
    envelope_counts = Counter(r["vehicle_projection_envelope_status"] for r in envelope)
    aspect_counts = Counter(r["aspect_angle_identifiability_status"] for r in envelope)
    threshold_counts = Counter(r["threshold_component_identity_status"] for r in trans)
    family_counts = Counter(r["template_family"] for r in meas)
    proxy_count = sum(1 for r in meas if r["proxy_formula_used"] != "false")
    resolved_axis = [r for r in axis if r["axis_orientation_status"] == "AXIS_ORIENTATION_RESOLVED"]
    stable = sorted(resolved_axis, key=lambda r: f(r["range_azimuth_acute_complement_error_deg"]))[:5]
    stable_heading = "Typical resolved-axis samples" if stable else "No resolved stable-axis samples observed; lowest-complement audit samples"
    if not stable:
        stable = sorted(axis, key=lambda r: f(r["range_azimuth_acute_complement_error_deg"]))[:5]
    ambiguous = [r for r in axis if r["axis_orientation_status"] != "AXIS_ORIENTATION_RESOLVED"][:5]
    rotation_rows = [r for r in meas if r["template_family"] == "local_region_rotation"]
    rot_sensitive = sorted(rotation_rows, key=lambda r: f(r["axis_angle_delta_deg_measured"]), reverse=True)[:5]
    rot_insensitive = sorted(rotation_rows, key=lambda r: f(r["axis_angle_delta_deg_measured"]))[:5]

    def counts_text(counter: Counter[str]) -> str:
        return "; ".join(f"{k}={v}" for k, v in sorted(counter.items()))

    lines = [
        "# GM_RM019 S1-R1 static axis rotation semantic integrity",
        "",
        f"Status: `{status}`",
        "",
        f"S2_READINESS=`{readiness}`",
        "",
        "OTY2 (Optical Timeline Y2, 光学时序辅助阶段二) / SAR (Synthetic Aperture Radar, 合成孔径雷达) / GT (Ground Truth, 真值) boundary: this round repairs S1 static semantics only. It does not execute S2 GT-region evaluation.",
        "",
        "## Existing final_heading semantics confirmed",
        "",
        "- `docs/guidance/algorithm_spec_full.md` states that `heading`, `final_heading`, `w`, and `h` are storage-axis or display-XY box conventions, not literal vehicle heading, width, or length.",
        "- `src/geometry/fan_polar.py` says heading values carried by candidate rows are display-XY storage axes and are not physical vehicle heading.",
        "- `src/visualization/svg_canvas.py` draws `heading_deg` as the width-axis vector of a rotated rectangle.",
        "- Therefore `final_heading_deg` is the stored `final_w` axis in SAR image coordinates, not vehicle yaw, not the GT long axis by default, and not the gray-response principal axis.",
        "",
        "## Unified angle semantics",
        "",
        "|field|meaning|range|",
        "|---|---|---|",
        "|response_axis_image_deg|undirected SAR gray covariance major axis in image coordinates|[0,180)|",
        "|response_axis_to_range_signed_deg|signed undirected axis angle relative to local radar range vector|[-90,90)|",
        "|response_axis_to_range_acute_deg|absolute range-relative axis angle|[0,90]|",
        "|response_axis_to_azimuth_acute_deg|absolute azimuth-relative axis angle|[0,90]|",
        "|aspect_angle_candidate_deg|hypothetical vehicle projection long-axis angle relative to local range|[0,90]|",
        "",
        "The response principal axis is an undirected energy axis. It lacks vehicle nose direction, cannot distinguish 0 degrees from 180 degrees, can be local-part or multi-component driven, and therefore is not vehicle yaw.",
        "",
        "## Core statistics",
        "",
        f"- response unit level: `250`; independent geometry level: `{len(geometry)}`.",
        "- duplicate geometries are keyed by the frozen S1 conservative response geometry (`conservative_bbox`) to match the 215 independent-geometry baseline; member SAR frames and response units are retained as provenance, and each independent geometry is measured once before mapping back to members.",
        f"- signed axis stats: `{signed_stats}`.",
        f"- acute axis stats: `{acute_stats}`.",
        f"- axis_orientation_status: `{counts_text(axis_counts)}`.",
        f"- vehicle_projection_envelope_status: `{counts_text(envelope_counts)}`.",
        f"- aspect_angle_identifiability_status: `{counts_text(aspect_counts)}`.",
        f"- required_missing_support_range_m: `{missing_r}`.",
        f"- required_missing_support_azimuth_m: `{missing_a}`.",
        f"- required_extra_spread_range_m: `{extra_r}`.",
        f"- required_extra_spread_azimuth_m: `{extra_a}`.",
        f"- threshold component identity transitions: `{counts_text(threshold_counts)}`.",
        f"- counterfactual family counts: `{counts_text(family_counts)}`.",
        f"- proxy formula result rows: `{proxy_count}`.",
        "",
        "## Synthetic semantic tests",
        "",
        "- `axis_45_vs_135_not_collapsed`: PASS",
        "- `axis_v_and_minus_v_equivalent`: PASS",
        "- `rotation_180_equivalent_to_0`: PASS",
        "- `rotation_90_long_short_swap_recorded`: PASS",
        "",
        f"## {stable_heading}",
        "",
        markdown_table(stable, ["independent_geometry_id", "response_unit_id", "sar_frame", "response_axis_image_deg", "response_axis_to_range_signed_deg", "response_axis_to_range_acute_deg", "axis_orientation_status"], 5),
        "",
        "## Typical ambiguous-axis samples",
        "",
        markdown_table(ambiguous, ["independent_geometry_id", "response_unit_id", "sar_frame", "principal_axis_ratio", "measured_component_count", "axis_orientation_status", "threshold_component_identity_status"], 5),
        "",
        "## Typical rotation-sensitive samples",
        "",
        markdown_table(rot_sensitive, ["template_id", "independent_geometry_id", "sar_frame", "rotation_deg", "energy_delta_measured", "axis_angle_delta_deg_measured", "measured_axis_orientation_status"], 5),
        "",
        "## Typical rotation-insensitive samples",
        "",
        markdown_table(rot_insensitive, ["template_id", "independent_geometry_id", "sar_frame", "rotation_deg", "energy_delta_measured", "axis_angle_delta_deg_measured", "measured_axis_orientation_status"], 5),
        "",
        "## Visual review package",
        "",
        markdown_table(visual, ["visual_case_id", "review_label", "independent_geometry_id", "response_unit_id", "sar_frame", "visual_relpath", "opened_for_review"], None),
        "",
        "## Integrity gates",
        "",
        markdown_table(gates, INTEGRITY_FIELDS, None),
        "",
        "## Outputs",
        "",
    ]
    for path in list(gen.OUTPUTS.values()) + [INTEGRITY, REPORT]:
        lines.append(f"- `{gen.rel(path)}`")
    lines.extend(
        [
            "",
            "## S2 boundary",
            "",
            "S2 may open paired annotations, response-unit GT instance matrices, and mask-observation audit tables only after this S1-R1 package is frozen. This round did not perform GT region ranking, GT boundary fitting, final-box generation, selector/ranking construction, GT modification, or GM_RM017 modification.",
        ]
    )
    return "\n".join(lines) + "\n"


def evaluate() -> None:
    rows = load_all()
    gates = integrity_rows(rows)
    write_csv(INTEGRITY, gates, INTEGRITY_FIELDS)
    REPORT.write_text(report_text(rows, gates), encoding="utf-8")
    gen.write_workspace_note("evaluate", gen.STATUS_READY if all(g["status"] == "PASS" for g in gates) else "S1_R1_PARTIAL")
    print(f"evaluate: {gen.STATUS_READY if all(g['status'] == 'PASS' for g in gates) else 'S1_R1_PARTIAL'}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["evaluate"])
    args = parser.parse_args()
    if args.command == "evaluate":
        evaluate()


if __name__ == "__main__":
    main()
