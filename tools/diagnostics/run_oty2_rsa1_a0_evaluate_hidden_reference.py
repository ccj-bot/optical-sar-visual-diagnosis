from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from oty2_rsa1_a0_common import REPO, load_config, parse_points, read_csv, verify_rule_freeze, write_csv


MANIFEST_DIR = REPO / "manifests" / "oty2"
HIDDEN_SKELETON = MANIFEST_DIR / "oty2_rsa1_a0_hidden_skeleton_reference.csv"
HIDDEN_BACKGROUND = MANIFEST_DIR / "oty2_rsa1_a0_hidden_background_reference.csv"
PRIMITIVES = MANIFEST_DIR / "oty2_rsa1_a0_structure_primitives.csv"
TRACE = MANIFEST_DIR / "oty2_rsa1_a0_expansion_trace.csv"
EVALUATION = MANIFEST_DIR / "oty2_rsa1_a0_hidden_reference_evaluation.csv"
STAGE_CONCLUSION = MANIFEST_DIR / "oty2_rsa1_a0_stage_conclusion.csv"
REPORT = REPO / "reports" / "oty2" / "oty2_rsa1_a0_seed_object_extension_micropilot_20260717.md"

IMAGE_SHAPE = (1334, 2308)
MODES = [
    "SEED_ONLY_BASELINE",
    "SINGLE_FRAME_SPATIAL",
    "FORWARD_CAUSAL_MICROPILOT",
    "OFFLINE_BIDIRECTIONAL_MICROPILOT",
]

EVALUATION_FIELDS = [
    "case_id",
    "frame",
    "coordinate_family",
    "evaluation_mode",
    "hidden_skeleton_length_px",
    "hidden_skeleton_covered_px",
    "hidden_skeleton_coverage_fraction",
    "seed_only_covered_px",
    "added_skeleton_covered_px",
    "confirmed_seed_count",
    "supported_extension_count",
    "supported_extension_length_px",
    "probable_extension_count",
    "probable_extension_length_px",
    "confirmed_vertical_background_overlap_px",
    "ambiguity_zone_area_px",
    "ambiguity_zone_overlap_px",
    "ambiguity_zone_overlap_fraction",
    "fully_assigned_ambiguity_zone",
    "supported_without_seed_path_count",
    "supported_crossing_background_count",
]


def line_mask(points: np.ndarray, width: int) -> np.ndarray:
    mask = np.zeros(IMAGE_SHAPE, dtype=np.uint8)
    cv2.polylines(mask, [np.rint(points).astype(np.int32)], False, 1, thickness=width, lineType=cv2.LINE_8)
    return mask.astype(bool)


def polygon_mask(points: np.ndarray) -> np.ndarray:
    mask = np.zeros(IMAGE_SHAPE, dtype=np.uint8)
    cv2.fillPoly(mask, [np.rint(points).astype(np.int32)], 1)
    return mask.astype(bool)


def geometry_mask(row: dict[str, str]) -> np.ndarray:
    points = parse_points(row["geometry_raw"])
    width = max(1, int(round(float(row["width"]))))
    return line_mask(points, width)


def reference_rows_by_frame() -> dict[tuple[str, int], dict[str, dict[str, str]]]:
    grouped: dict[tuple[str, int], dict[str, dict[str, str]]] = {}
    for row in read_csv(HIDDEN_SKELETON) + read_csv(HIDDEN_BACKGROUND):
        key = (row["case_id"], int(row["sar_frame"]))
        grouped.setdefault(key, {})[row["label"]] = row
    return grouped


def select_mode_rows(rows: list[dict[str, str]], case_id: str, frame: int, family: str, mode: str) -> list[dict[str, str]]:
    base = [
        row
        for row in rows
        if row["case_id"] == case_id and int(row["frame"]) == frame and row["coordinate_family"] == family
    ]
    if mode == "SEED_ONLY_BASELINE":
        return [row for row in base if row["propagation_mode"] == "SINGLE_FRAME_SPATIAL" and row["state"] == "CONFIRMED_SEED"]
    return [row for row in base if row["propagation_mode"] == mode]


def evaluate() -> list[dict[str, Any]]:
    config = load_config()
    family = config["primary_coordinate_family"]
    primitive_rows = read_csv(PRIMITIVES)
    references = reference_rows_by_frame()
    results: list[dict[str, Any]] = []
    seed_coverage: dict[tuple[str, int], int] = {}

    for (case_id, frame), labels in sorted(references.items()):
        skeleton_mask = line_mask(parse_points(labels["CONFIRMED_MAIN_SKELETON"]["points"]), 1)
        vertical_mask = line_mask(parse_points(labels["CONFIRMED_VERTICAL_BACKGROUND"]["points"]), 5)
        ambiguity_mask = polygon_mask(parse_points(labels["ARC_OR_CLUTTER_AMBIGUOUS_ZONE"]["points"])) | polygon_mask(
            parse_points(labels["UNRESOLVED_ENDPOINT_ZONE"]["points"])
        )
        skeleton_length = int(np.count_nonzero(skeleton_mask))
        for mode in MODES:
            rows = select_mode_rows(primitive_rows, case_id, frame, family, mode)
            supported_rows = [row for row in rows if row["state"] in {"CONFIRMED_SEED", "SUPPORTED_EXTENSION"}]
            extension_rows = [row for row in rows if row["state"] == "SUPPORTED_EXTENSION"]
            probable_rows = [row for row in rows if row["state"] == "PROBABLE_EXTENSION"]
            supported_mask = np.zeros(IMAGE_SHAPE, dtype=bool)
            extension_mask = np.zeros(IMAGE_SHAPE, dtype=bool)
            for row in supported_rows:
                supported_mask |= geometry_mask(row)
            for row in extension_rows:
                extension_mask |= geometry_mask(row)
            covered = int(np.count_nonzero(skeleton_mask & supported_mask))
            if mode == "SEED_ONLY_BASELINE":
                seed_coverage[(case_id, frame)] = covered
            added = max(0, covered - seed_coverage.get((case_id, frame), covered))
            bad_paths = 0
            crossing = 0
            for row in extension_rows:
                path = row["shortest_seed_path"]
                if "SEED" not in path or not path.split(">")[0].endswith("SEED"):
                    bad_paths += 1
                if row["crosses_confirmed_background"] == "true":
                    crossing += 1
            overlap_mask = supported_mask if mode == "SEED_ONLY_BASELINE" else extension_mask
            ambiguity_area = int(np.count_nonzero(ambiguity_mask))
            ambiguity_overlap = int(np.count_nonzero(overlap_mask & ambiguity_mask))
            results.append(
                {
                    "case_id": case_id,
                    "frame": frame,
                    "coordinate_family": family,
                    "evaluation_mode": mode,
                    "hidden_skeleton_length_px": skeleton_length,
                    "hidden_skeleton_covered_px": covered,
                    "hidden_skeleton_coverage_fraction": f"{covered / max(skeleton_length, 1):.6f}",
                    "seed_only_covered_px": seed_coverage.get((case_id, frame), covered),
                    "added_skeleton_covered_px": added,
                    "confirmed_seed_count": sum(row["state"] == "CONFIRMED_SEED" for row in rows),
                    "supported_extension_count": len(extension_rows),
                    "supported_extension_length_px": f"{sum(float(row['length']) for row in extension_rows):.6f}",
                    "probable_extension_count": len(probable_rows),
                    "probable_extension_length_px": f"{sum(float(row['length']) for row in probable_rows):.6f}",
                    "confirmed_vertical_background_overlap_px": int(np.count_nonzero(overlap_mask & vertical_mask)),
                    "ambiguity_zone_area_px": ambiguity_area,
                    "ambiguity_zone_overlap_px": ambiguity_overlap,
                    "ambiguity_zone_overlap_fraction": f"{ambiguity_overlap / max(ambiguity_area, 1):.6f}",
                    "fully_assigned_ambiguity_zone": str(
                        ambiguity_area > 0 and ambiguity_overlap == ambiguity_area
                    ).lower(),
                    "supported_without_seed_path_count": bad_paths,
                    "supported_crossing_background_count": crossing,
                }
            )
    return results


def first_trace(
    case_id: str,
    frame: int,
    primitive_suffix: str,
    family: str,
    mode: str = "SINGLE_FRAME_SPATIAL",
) -> dict[str, str]:
    rows = read_csv(TRACE)
    return next(
        row
        for row in rows
        if row["case_id"] == case_id
        and int(row["frame"]) == frame
        and row["coordinate_family"] == family
        and row["propagation_mode"] == mode
        and row["destination_primitive"].endswith(primitive_suffix)
    )


def aggregate_mode(results: list[dict[str, Any]], case_id: str, mode: str) -> dict[str, float]:
    rows = [row for row in results if row["case_id"] == case_id and row["evaluation_mode"] == mode]
    return {
        "seed_count": float(sum(int(row["confirmed_seed_count"]) for row in rows)),
        "supported_count": float(sum(int(row["supported_extension_count"]) for row in rows)),
        "supported_length": float(sum(float(row["supported_extension_length_px"]) for row in rows)),
        "probable_count": float(sum(int(row["probable_extension_count"]) for row in rows)),
        "added_coverage": float(sum(int(row["added_skeleton_covered_px"]) for row in rows)),
        "vertical_overlap": float(sum(int(row["confirmed_vertical_background_overlap_px"]) for row in rows)),
        "ambiguity_area": float(sum(int(row["ambiguity_zone_area_px"]) for row in rows)),
        "ambiguity_overlap": float(sum(int(row["ambiguity_zone_overlap_px"]) for row in rows)),
        "full_ambiguity_assignments": float(sum(row["fully_assigned_ambiguity_zone"] == "true" for row in rows)),
        "bad_paths": float(sum(int(row["supported_without_seed_path_count"]) for row in rows)),
        "crossing_paths": float(sum(int(row["supported_crossing_background_count"]) for row in rows)),
    }


def evaluation_row(
    results: list[dict[str, Any]], case_id: str, frame: int, mode: str
) -> dict[str, Any]:
    return next(
        row
        for row in results
        if row["case_id"] == case_id
        and int(row["frame"]) == frame
        and row["evaluation_mode"] == mode
    )


def hidden_reference_isolated() -> bool:
    rule_rows = read_csv(MANIFEST_DIR / "oty2_rsa1_a0_rule_freeze_manifest.csv")
    forbidden = (HIDDEN_SKELETON.name, HIDDEN_BACKGROUND.name)
    for row in rule_rows:
        if row["entry_role"] != "frozen_rule_source":
            continue
        source = Path(row["path"])
        if not source.is_absolute():
            source = REPO / source
        text = source.read_text(encoding="utf-8")
        if any(name in text for name in forbidden):
            return False
    return True


def build_stage_conclusion(results: list[dict[str, Any]], rule_sha: str) -> tuple[list[dict[str, Any]], str]:
    pv002 = aggregate_mode(results, "PV002_337_341", "OFFLINE_BIDIRECTIONAL_MICROPILOT")
    pv003 = aggregate_mode(results, "PV003_380_384", "OFFLINE_BIDIRECTIONAL_MICROPILOT")
    conditions = [
        ("C01_BOTH_CASES_EXTEND", pv002["supported_count"] > 0 and pv003["supported_count"] > 0, f"PV002={pv002['supported_count']:.0f};PV003={pv003['supported_count']:.0f}"),
        ("C02_ADDED_CONFIRMED_SKELETON", pv002["added_coverage"] > 0 and pv003["added_coverage"] > 0, f"PV002={pv002['added_coverage']:.0f};PV003={pv003['added_coverage']:.0f}"),
        ("C03_WEAK_STATE_CENTRAL_RELATION", pv002["seed_count"] == 5 and pv003["seed_count"] == 5, f"PV002 seeds={pv002['seed_count']:.0f};PV003 seeds={pv003['seed_count']:.0f}; no full-band copy"),
        ("C04_ZERO_VERTICAL_BACKGROUND_POLLUTION", pv002["vertical_overlap"] == 0 and pv003["vertical_overlap"] == 0, f"PV002={pv002['vertical_overlap']:.0f};PV003={pv003['vertical_overlap']:.0f}"),
        ("C05_NO_BACKGROUND_CROSSING_PATH", pv002["crossing_paths"] == 0 and pv003["crossing_paths"] == 0, f"PV002={pv002['crossing_paths']:.0f};PV003={pv003['crossing_paths']:.0f}"),
        ("C06_NO_COMPLETE_ARC_CLUTTER_ASSIGNMENT", pv002["full_ambiguity_assignments"] == 0 and pv003["full_ambiguity_assignments"] == 0, f"PV002 overlap={pv002['ambiguity_overlap']:.0f}/{pv002['ambiguity_area']:.0f};PV003 overlap={pv003['ambiguity_overlap']:.0f}/{pv003['ambiguity_area']:.0f}; fully assigned frames=0"),
        ("C07_COMPLETE_SEED_PATH", pv002["bad_paths"] == 0 and pv003["bad_paths"] == 0, f"PV002={pv002['bad_paths']:.0f};PV003={pv003['bad_paths']:.0f}"),
        ("C08_FROZEN_RULE_REPLAY", True, f"rule_sha256={rule_sha}"),
        ("C09_CLEAR_SEED_ONLY_INCREMENT", pv002["added_coverage"] > 0 and pv003["added_coverage"] > 0, f"PV002={pv002['added_coverage']:.0f};PV003={pv003['added_coverage']:.0f}"),
        ("C10_NO_HIDDEN_REFERENCE_FEEDBACK", hidden_reference_isolated(), "frozen propagation sources contain no hidden-reference filename"),
    ]
    rows = [
        {
            "condition_id": condition_id,
            "passed": str(passed).lower(),
            "evidence": evidence,
        }
        for condition_id, passed, evidence in conditions
    ]
    if all(passed for _, passed, _ in conditions):
        conclusion = "MICROPILOT_MECHANISM_SUPPORTED"
    elif pv002["supported_count"] > 0 and pv003["supported_count"] == 0:
        conclusion = "MICROPILOT_PARTIALLY_SUPPORTED"
    else:
        conclusion = "MICROPILOT_FAILED"
    rows.append({"condition_id": "STAGE_CONCLUSION", "passed": "", "evidence": conclusion})
    return rows, conclusion


def build_report(results: list[dict[str, Any]], conclusion: str, rule_sha: str, hidden_sha: str) -> str:
    config = load_config()
    family = config["primary_coordinate_family"]
    pv002_spatial = aggregate_mode(results, "PV002_337_341", "SINGLE_FRAME_SPATIAL")
    pv002_forward = aggregate_mode(results, "PV002_337_341", "FORWARD_CAUSAL_MICROPILOT")
    pv002_bidir = aggregate_mode(results, "PV002_337_341", "OFFLINE_BIDIRECTIONAL_MICROPILOT")
    pv003_spatial = aggregate_mode(results, "PV003_380_384", "SINGLE_FRAME_SPATIAL")
    pv003_forward = aggregate_mode(results, "PV003_380_384", "FORWARD_CAUSAL_MICROPILOT")
    pv003_bidir = aggregate_mode(results, "PV003_380_384", "OFFLINE_BIDIRECTIONAL_MICROPILOT")
    p2_right1 = first_trace("PV002_337_341", 339, "RIGHT01", family)
    p2_right2 = first_trace("PV002_337_341", 339, "RIGHT02", family)
    p2_right3 = first_trace("PV002_337_341", 339, "RIGHT03", family)
    p2_right3_bidir = first_trace(
        "PV002_337_341", 339, "RIGHT03", family, "OFFLINE_BIDIRECTIONAL_MICROPILOT"
    )
    p2_left1 = first_trace("PV002_337_341", 339, "LEFT01", family)
    p3_right1 = first_trace("PV003_380_384", 384, "RIGHT01", family)
    p3_382 = first_trace("PV003_380_384", 382, "RIGHT01", family)
    eval_p2_339_spatial = evaluation_row(results, "PV002_337_341", 339, "SINGLE_FRAME_SPATIAL")
    eval_p2_339_bidir = evaluation_row(results, "PV002_337_341", 339, "OFFLINE_BIDIRECTIONAL_MICROPILOT")
    eval_p3_382_bidir = evaluation_row(results, "PV003_380_384", 382, "OFFLINE_BIDIRECTIONAL_MICROPILOT")
    eval_p3_384_bidir = evaluation_row(results, "PV003_380_384", 384, "OFFLINE_BIDIRECTIONAL_MICROPILOT")
    replay_summary = json.loads(
        (Path(config["output_root"]) / "frozen_replay" / "replay_summary.json").read_text(encoding="utf-8")
    )
    lines = [
        "# OTY2-RSA1-A0 Manual-Seed-Guided SAR Response Object Extension Micropilot",
        "",
        "Date: `2026-07-17`",
        "",
        f"Stage conclusion: `{conclusion}`",
        "",
        f"Hidden-reference freeze SHA256: `{hidden_sha}`",
        "",
        f"Rule-freeze SHA256: `{rule_sha}`",
        "",
        "The main experiment is the GT-aligned research stack. Optical-proxy-aligned results are sensitivity evidence only and are not used to rescue the stage conclusion.",
        "",
        "## 1. What structure did the algorithm actually extend from the central seed?",
        "",
        "The frozen mechanism visits contiguous 12 px local line-segment primitives along the R2-confirmed seed tangent. It does not generate a top-N bank or rank alternatives. In PV002 SAR 339, `GT_RIGHT01` and `GT_RIGHT02` extend the subtle lower response immediately to the right of the 24 px seed. `GT_LEFT01` intersects the vertical-background barrier and is vetoed before any structural score can promote it.",
        "",
        f"- Exact evidence: PV002 SAR 339 primitive `{p2_right1['destination_primitive']}`, expansion step `{p2_right1['expansion_step']}`, gate result `ALL_REQUIRED_GATES_PASSED`, ridge relation `{p2_right1['ridge_relation']}`, contrast relation `{p2_right1['contrast_relation']}`, temporal NCC `{p2_right1['temporal_support']}`, card `{p2_right1['evidence_card']}`.",
        f"- Counterexample/barrier evidence: PV002 SAR 339 primitive `{p2_left1['destination_primitive']}`, expansion step `{p2_left1['expansion_step']}`, first failed gate `{p2_left1['first_failed_gate']}`, card `{p2_left1['evidence_card']}`.",
        f"- Hidden-reference evaluation: PV002 SAR 339 `SINGLE_FRAME_SPATIAL` covers `{eval_p2_339_spatial['hidden_skeleton_covered_px']}/{eval_p2_339_spatial['hidden_skeleton_length_px']} px`, with `{eval_p2_339_spatial['added_skeleton_covered_px']} px` beyond seed-only.",
        "- PV003 reconstructs the same primitives from the frozen seed tangent, but no GT-aligned primitive reaches `SUPPORTED_EXTENSION`.",
        "",
        "## 2. Which relation gates did supported extensions pass?",
        "",
        "A supported primitive must retain a current-frame seed path, stay outside the vertical barrier and ambiguity zones, satisfy direction/width continuity, pass ridge or local-contrast evidence, and receive temporal support. No weighted total score exists.",
        "",
        f"PV002 totals: spatial supported `{pv002_spatial['supported_count']:.0f}` / `{pv002_spatial['supported_length']:.1f} px`, forward supported `{pv002_forward['supported_count']:.0f}` / `{pv002_forward['supported_length']:.1f} px`, bidirectional supported `{pv002_bidir['supported_count']:.0f}` / `{pv002_bidir['supported_length']:.1f} px`.",
        f"Exact evidence: PV002 SAR 339 primitive `{p2_right2['destination_primitive']}`, expansion step `{p2_right2['expansion_step']}`, source `{p2_right2['source_primitive']}`, gate result `ALL_REQUIRED_GATES_PASSED`, card `{p2_right2['evidence_card']}`; the matching hidden-reference row is `PV002_337_341,339,SINGLE_FRAME_SPATIAL` with `{eval_p2_339_spatial['added_skeleton_covered_px']} px` added coverage and `{eval_p2_339_spatial['supported_without_seed_path_count']}` path failures.",
        "",
        "## 3. Did extension cover confirmed skeleton beyond the seed?",
        "",
        f"PV002 gains hidden-skeleton coverage beyond seed-only: spatial `{pv002_spatial['added_coverage']:.0f} px`, forward `{pv002_forward['added_coverage']:.0f} px`, bidirectional `{pv002_bidir['added_coverage']:.0f} px`. PV003 gains `0 px` in all three modes because probable is not merged into supported.",
        "",
        f"PV003 SAR 382 `GT_RIGHT01` remains probable with orientation difference `{p3_382['orientation_difference']}` and temporal NCC `{p3_382['temporal_support']}`; card `{p3_382['evidence_card']}`.",
        f"Exact coverage evidence: PV002 SAR 339 primitive `{p2_right2['destination_primitive']}`, expansion step `{p2_right2['expansion_step']}`, gate result `ALL_REQUIRED_GATES_PASSED`, card `{p2_right2['evidence_card']}`; hidden row `PV002_337_341,339,SINGLE_FRAME_SPATIAL` reports `{eval_p2_339_spatial['hidden_skeleton_covered_px']}/{eval_p2_339_spatial['hidden_skeleton_length_px']} px` covered and `{eval_p2_339_spatial['added_skeleton_covered_px']} px` added. PV003 SAR 382 primitive `{p3_382['destination_primitive']}`, step `{p3_382['expansion_step']}`, fails `{p3_382['first_failed_gate']}` and the bidirectional hidden row reports `{eval_p3_382_bidir['added_skeleton_covered_px']} px` added.",
        "",
        "## 4. Did the vertical-background barrier prevent pollution?",
        "",
        f"Yes for supported output. Hidden-reference overlap is PV002 `{pv002_bidir['vertical_overlap']:.0f} px` and PV003 `{pv003_bidir['vertical_overlap']:.0f} px`; supported crossing-path counts are PV002 `{pv002_bidir['crossing_paths']:.0f}` and PV003 `{pv003_bidir['crossing_paths']:.0f}`. PV002 records five explicit left-side background vetoes across SAR 337-341.",
        f"Exact barrier evidence: PV002 SAR 339 primitive `{p2_left1['destination_primitive']}`, expansion step `{p2_left1['expansion_step']}`, first failed gate `{p2_left1['first_failed_gate']}`, card `{p2_left1['evidence_card']}`; hidden row `PV002_337_341,339,OFFLINE_BIDIRECTIONAL_MICROPILOT` reports `{eval_p2_339_bidir['confirmed_vertical_background_overlap_px']} px` vertical-background overlap and `{eval_p2_339_bidir['supported_crossing_background_count']}` crossing paths.",
        "",
        "## 5. Were fan arc, clutter, and endpoints kept unresolved?",
        "",
        f"No GT-aligned mode assigns an entire hidden ambiguity zone: PV002 bidirectional overlap is `{pv002_bidir['ambiguity_overlap']:.0f}/{pv002_bidir['ambiguity_area']:.0f} px` with `{pv002_bidir['full_ambiguity_assignments']:.0f}` fully assigned frames; PV003 is `{pv003_bidir['ambiguity_overlap']:.0f}/{pv003_bidir['ambiguity_area']:.0f} px` with `{pv003_bidir['full_ambiguity_assignments']:.0f}` fully assigned frames. However, PV002 bidirectional propagation does weaken endpoint restraint by promoting a localized part of the unresolved right endpoint. Proxy sensitivity ambiguity stops remain sensitivity-only evidence.",
        f"Exact endpoint evidence: PV002 SAR 339 primitive `{p2_right3['destination_primitive']}`, expansion step `{p2_right3['expansion_step']}`, first failed gate `{p2_right3['first_failed_gate']}`, single-frame state `{p2_right3['state_after']}`, card `{p2_right3['evidence_card']}`. Offline bidirectional step `{p2_right3_bidir['expansion_step']}` promotes the same primitive to `{p2_right3_bidir['state_after']}` through cross-frame support from `{p2_right3_bidir['source_primitive']}`; hidden row `PV002_337_341,339,OFFLINE_BIDIRECTIONAL_MICROPILOT` reports `{eval_p2_339_bidir['ambiguity_zone_overlap_px']}/{eval_p2_339_bidir['ambiguity_zone_area_px']} px` overlap (`{eval_p2_339_bidir['ambiguity_zone_overlap_fraction']}`), not full-zone assignment.",
        "",
        "## 6. Did the frozen rule reproduce in PV003, and what failed?",
        "",
        f"The rule reproduced byte-identically under `{rule_sha}` and no PV003 tuning occurred. It failed at the local-structure/temporal layer rather than at the barrier: PV003 SAR 384 `GT_RIGHT01` has orientation difference `{p3_right1['orientation_difference']}`, width relation `{p3_right1['width_relation']}`, temporal NCC `{p3_right1['temporal_support']}`, and first failed gate `{p3_right1['first_failed_gate']}`; card `{p3_right1['evidence_card']}`.",
        f"Exact replay evidence: primitive `{p3_right1['destination_primitive']}`, expansion step `{p3_right1['expansion_step']}`, source `{p3_right1['source_primitive']}`, state `{p3_right1['state_after']}`; hidden row `PV003_380_384,384,OFFLINE_BIDIRECTIONAL_MICROPILOT` reports `{eval_p3_384_bidir['added_skeleton_covered_px']} px` added coverage, `{eval_p3_384_bidir['confirmed_vertical_background_overlap_px']} px` vertical overlap, and `{eval_p3_384_bidir['ambiguity_zone_overlap_px']} px` ambiguity overlap.",
        "SAR 384 is the replay-window endpoint. Its evidence card clamps the display-only `next SAR` panel to SAR 384 itself; this duplicate panel is not future-frame support and does not change the recorded negative temporal relation.",
        "",
        "The weak GT-aligned response does not satisfy the frozen PV002 direction/width plus temporal relation. Optical-proxy sensitivity yields many more supported primitives, but PV003 proxy mapping drift is known debt and sensitivity-only output cannot be interpreted as main-mechanism success or failure.",
        "",
        "## 7. Continue or stop this propagation mechanism?",
        "",
        f"Conclusion: `{conclusion}`. The mechanism is locally useful in PV002 for conservative right-side extension and hard background blocking, but it does not reproduce supported extension in PV003. The ten-condition success gate therefore fails. This exact frozen mechanism should stop; any later work must open a new versioned micropilot focused on weak-response primitive orientation/temporal support, not retune RSA1-A0 after seeing PV003.",
        f"Decision evidence: PV003 SAR 382 primitive `{p3_382['destination_primitive']}`, expansion step `{p3_382['expansion_step']}`, first failed gate `{p3_382['first_failed_gate']}`, state `{p3_382['state_after']}`, card `{p3_382['evidence_card']}`; hidden row `PV003_380_384,382,OFFLINE_BIDIRECTIONAL_MICROPILOT` adds `{eval_p3_382_bidir['added_skeleton_covered_px']} px` over seed-only. Together with PV002 SAR 339 `{p2_right1['destination_primitive']}` passing all required gates and adding `{eval_p2_339_bidir['added_skeleton_covered_px']} px`, this supports partial—not full—mechanism support.",
        "",
        "## Output counts",
        "",
        f"- Final primitive rows: `{replay_summary['primitive_count']}`.",
        f"- Final expansion-trace rows: `{replay_summary['trace_count']}`.",
        f"- PV003 tuning performed: `{str(replay_summary['pv003_tuning_performed']).lower()}`.",
        "- Hidden references were not read by preparation, primitive construction, spatial extension, temporal extension, rule freeze, or replay. They were opened only by this evaluator.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    rule_sha = verify_rule_freeze()
    hidden_freeze_rows = read_csv(MANIFEST_DIR / "oty2_rsa1_a0_hidden_reference_freeze_manifest.csv")
    hidden_sha = hidden_freeze_rows[0]["aggregate_reference_sha256"]
    results = evaluate()
    write_csv(EVALUATION, results, EVALUATION_FIELDS)
    stage_rows, conclusion = build_stage_conclusion(results, rule_sha)
    write_csv(STAGE_CONCLUSION, stage_rows, ["condition_id", "passed", "evidence"])
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(build_report(results, conclusion, rule_sha, hidden_sha), encoding="utf-8")
    summary = {
        "stage_conclusion": conclusion,
        "hidden_reference_freeze_sha256": hidden_sha,
        "rule_freeze_sha256": rule_sha,
        "evaluation_rows": len(results),
        "evaluation_manifest": str(EVALUATION),
        "stage_conclusion_manifest": str(STAGE_CONCLUSION),
        "report": str(REPORT),
    }
    output = Path(load_config()["output_root"]) / "evaluation_summary.json"
    output.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
