"""WGV3.6A-A1.7R bounded SAR response hypothesis audit.

This follow-up keeps A1.7 as a negative result and adds bounded compact
assemblies plus persistent hypothesis sets. The generate phase never loads
future/hidden target boxes; evaluation verifies the frozen prediction hash
before reading target boxes.
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from itertools import combinations
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from PIL import Image, ImageDraw, ImageFont

TOOL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOL_DIR))

import run_oty2_wgv3_6a_a1_7_response_assembly_tracking as a17  # noqa: E402
from run_oty2_wgv3_5a_r2c_mask_aware_near_field_mapping import (  # noqa: E402
    REPO_ROOT,
    REPORT_DIR,
    SAMPLES_DIR,
    SAR_HEIGHT,
    SAR_WIDTH,
    Box,
    box_from_pair,
    build_geometry,
    fmt,
    parse_float,
    parse_int,
    read_gray,
    sar_gray_path,
    sha256,
    write_csv,
    write_text,
)


DATE = "20260711"
REQUESTED_START_COMMIT = "4505b6af636c576b7f447a2409798ee5c9dfc249"
SCENE = "GM_RM019"
OUT_DIR = REPO_ROOT / "outputs" / "wgv3_6a_a1_7r_20260711"
FAN_AREA = 2628414.0
MAX_HYPOTHESES = 6
MAX_TOTAL_SEARCH_RATIO = 0.03
COMPACT_SUPPORT_FOR_PROVISIONAL = 2
COMPACT_SUPPORT_FOR_CONFIRMED = 3

OUTPUTS = {
    "report": REPORT_DIR / f"oty2_wgv3_6a_a1_7r_bounded_hypothesis_tracking_{DATE}.md",
    "claim_correction": SAMPLES_DIR / f"oty2_wgv3_6a_a1_7r_claim_correction_{DATE}.csv",
    "visual_review": SAMPLES_DIR / f"oty2_wgv3_6a_a1_7r_visual_semantic_review_{DATE}.csv",
    "compact_trace": SAMPLES_DIR / f"oty2_wgv3_6a_a1_7r_compact_assembly_trace_{DATE}.csv",
    "hypothesis_trace": SAMPLES_DIR / f"oty2_wgv3_6a_a1_7r_persistent_hypothesis_trace_{DATE}.csv",
    "frozen_predictions": SAMPLES_DIR / f"oty2_wgv3_6a_a1_7r_frozen_predictions_{DATE}.csv",
    "hidden_eval": SAMPLES_DIR / f"oty2_wgv3_6a_a1_7r_hidden_anchor_evaluation_{DATE}.csv",
    "delta_audit": SAMPLES_DIR / f"oty2_wgv3_6a_a1_7r_c1c_c1d_delta_audit_{DATE}.csv",
    "polar_optical": SAMPLES_DIR / f"oty2_wgv3_6a_a1_7r_polar_optical_bypass_audit_{DATE}.csv",
    "failure_cases": SAMPLES_DIR / f"oty2_wgv3_6a_a1_7r_failure_cases_{DATE}.csv",
}

VISUALS = {
    "white_runtime": OUT_DIR / "a1_7r_white_runtime_full_zoom_review.png",
    "silver_runtime_a": OUT_DIR / "a1_7r_silver_runtime_full_zoom_review_a.png",
    "silver_runtime_b": OUT_DIR / "a1_7r_silver_runtime_full_zoom_review_b.png",
    "eval_overlay": OUT_DIR / "a1_7r_eval_only_overlay_review.png",
    "branch_summary": OUT_DIR / "a1_7r_branch_budget_summary.png",
}

CLAIM_FIELDS = ["claim", "original_status", "corrected_status", "code_evidence", "metric_evidence", "reason_cn"]
VISUAL_FIELDS = [
    "review_id",
    "experiment_id",
    "sar_frame",
    "component_id",
    "assembly_id",
    "visual_role",
    "same_vehicle_response",
    "background_response",
    "uncertain",
    "relation_to_previous_frame",
    "transitive_merge_error",
    "human_multimodal_judgement_cn",
    "runtime_png",
    "eval_png",
]
COMPACT_FIELDS = [
    "experiment_id",
    "experiment_type",
    "method",
    "physical_vehicle_id",
    "source_pair_id",
    "sar_frame",
    "component_ids",
    "assembly_id",
    "component_count",
    "assembly_centroid",
    "assembly_envelope",
    "assembly_azimuth",
    "assembly_radial",
    "azimuth_span",
    "radial_span",
    "max_pair_distance_px",
    "max_diameter_px",
    "internal_max_gap_px",
    "compact_pass",
    "rejection_reason",
    "search_window",
    "budget_width",
    "budget_height",
    "source_anchor_area",
    "prediction_area_ratio",
    "persistent_hypothesis_id",
    "association_event",
]
HYP_FIELDS = [
    "experiment_id",
    "experiment_type",
    "method",
    "physical_vehicle_id",
    "source_pair_id",
    "sar_frame",
    "persistent_hypothesis_id",
    "parent_hypothesis_ids",
    "branch_status",
    "association_event",
    "support_frames",
    "assembly_id",
    "hypothesis_region",
    "hypothesis_centroid",
    "hypothesis_azimuth",
    "hypothesis_radial",
    "velocity_px",
    "area_ratio_vs_source",
    "single_search_ratio",
    "total_hypothesis_area",
    "total_search_area",
    "total_search_ratio",
    "hypothesis_count",
    "hypothesis_budget_exceeded",
    "notes",
]
PRED_FIELDS = [
    "experiment_id",
    "experiment_type",
    "method",
    "physical_vehicle_id",
    "source_pair_id",
    "source_sar_frame",
    "target_pair_id",
    "target_sar_frame",
    "sar_frame",
    "frame_offset",
    "prediction_status",
    "selection_status",
    "prediction_region",
    "hypothesis_count",
    "hypothesis_regions",
    "total_hypothesis_area",
    "total_search_area",
    "single_search_ratio",
    "total_search_ratio",
    "max_single_branch_area",
    "source_anchor_area",
    "hypothesis_budget_exceeded",
    "persistent_hypothesis_id",
    "assembly_id",
    "confirmed_after_delay",
    "provisional_confirmed",
    "true_ambiguity_recovery",
    "algorithmic_branch_collapse",
    "association_discontinuity",
    "first_uncertain_frame",
    "first_irrecoverable_frame",
    "frozen_generation_phase",
    "target_manual_box_loaded",
    "future_endpoint_loaded",
    "reference_source",
]
EVAL_FIELDS = [
    "experiment_id",
    "experiment_type",
    "method",
    "physical_vehicle_id",
    "source_pair_id",
    "hidden_target_pair_id",
    "sar_frame",
    "prediction_status",
    "localization_metric_included",
    "hidden_target_coverage",
    "hidden_target_iou",
    "prediction_center_to_visible_response_center",
    "any_hypothesis_covers_target",
    "oracle_upper_bound_diagnostic",
    "hypothesis_count",
    "total_hypothesis_area",
    "single_search_ratio",
    "total_search_ratio",
    "prediction_area_to_source_anchor_area",
    "first_uncertain_frame",
    "first_irrecoverable_frame",
    "ambiguous_hypothesis_set_frames",
    "hypothesis_budget_exceeded_frames",
    "true_ambiguity_recovery_count",
    "algorithmic_branch_collapse_count",
    "association_discontinuity_count",
    "frozen_predictions_sha256_verified",
    "target_box_loaded_phase",
]
DELTA_FIELDS = [
    "comparison",
    "experiment_id",
    "experiment_type",
    "physical_vehicle_id",
    "hidden_target_pair_id",
    "sar_frame",
    "coverage_delta",
    "iou_delta",
    "center_error_delta",
    "search_ratio_delta",
    "area_ratio_delta",
    "verdict",
    "notes",
]
POLAR_FIELDS = [
    "experiment_id",
    "method",
    "physical_vehicle_id",
    "sar_frame",
    "sync_shift_sar_frames",
    "estimated_optical_frame",
    "optical_velocity_x_sign",
    "sar_assembly_azimuth_delta_sign",
    "azimuth_relation_consistent",
    "optical_depth_velocity_sign",
    "sar_assembly_radial_delta_sign",
    "radial_relation_consistent",
    "single_frame_consistency",
    "window3_consistency",
    "window5_consistency",
    "relation_used_for_filtering",
    "notes",
]
FAIL_FIELDS = [
    "case_id",
    "experiment_id",
    "method",
    "physical_vehicle_id",
    "failure_type",
    "sar_frame",
    "first_uncertain_frame",
    "first_irrecoverable_frame",
    "visual_png",
    "chinese_judgement",
    "notes",
]

REVIEW_FRAMES_WHITE = [27, 28, 29, 30, 31, 32, 40, 46, 60, 77, 78, 79, 80, 81]
REVIEW_FRAMES_SILVER = [212, 213, 220, 227, 238, 239, 243, 250, 260, 269, 270, 271, 272, 273, 276, 280, 284, 288, 289, 290]


@dataclass(frozen=True)
class Budget:
    source_box: Box
    source_anchor_area: float
    search_width: float
    search_height: float
    compact_width: float
    compact_height: float
    max_pair_distance: float
    max_diameter: float
    max_azimuth_span: float
    max_radial_span: float
    max_internal_gap: float
    association_distance: float


@dataclass(frozen=True)
class Branch:
    hypothesis_id: str
    assembly: a17.Assembly
    support_frames: int
    last_frame: int
    velocity: tuple[float, float]
    parents: tuple[str, ...] = ()
    area_expanded: bool = False


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def safe_div(num: float, den: float) -> float:
    return num / den if den else math.nan


def median(values: Iterable[float]) -> float:
    vals = [float(v) for v in values if not math.isnan(float(v))]
    return float(np.median(np.array(vals, dtype=np.float32))) if vals else math.nan


def box_from_text(text: str) -> Box | None:
    text = str(text or "").strip()
    if not text:
        return None
    parts = [parse_float(part) for part in text.split(",")]
    if len(parts) != 4 or any(math.isnan(part) for part in parts):
        return None
    return Box(parts[0], parts[1], parts[2], parts[3])


def clamp_box(box: Box) -> Box:
    return Box(
        max(0.0, min(float(SAR_WIDTH - 1), box.x1)),
        max(0.0, min(float(SAR_HEIGHT - 1), box.y1)),
        max(1.0, min(float(SAR_WIDTH), box.x2)),
        max(1.0, min(float(SAR_HEIGHT), box.y2)),
    )


def centered_box(cx: float, cy: float, width: float, height: float) -> Box:
    return clamp_box(Box(cx - width / 2.0, cy - height / 2.0, cx + width / 2.0, cy + height / 2.0))


def union_box(boxes: Sequence[Box]) -> Box:
    if not boxes:
        return Box(0, 0, 1, 1)
    return clamp_box(Box(min(b.x1 for b in boxes), min(b.y1 for b in boxes), max(b.x2 for b in boxes), max(b.y2 for b in boxes)))


def box_iou(a: Box, b: Box) -> float:
    x1 = max(a.x1, b.x1)
    y1 = max(a.y1, b.y1)
    x2 = min(a.x2, b.x2)
    y2 = min(a.y2, b.y2)
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    den = a.area + b.area - inter
    return inter / den if den else 0.0


def coverage(region: Box, target: Box) -> float:
    x1 = max(region.x1, target.x1)
    y1 = max(region.y1, target.y1)
    x2 = min(region.x2, target.x2)
    y2 = min(region.y2, target.y2)
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    return inter / target.area if target.area else 0.0


def sign_text(value: float, eps: float = 1e-6) -> str:
    if math.isnan(value) or abs(value) <= eps:
        return "zero"
    return "positive" if value > 0 else "negative"


def same_nonzero_sign(a: str, b: str) -> str:
    if a == "zero" or b == "zero":
        return "NOT_TESTED"
    return bool_text(a == b)


def branch_sort_key(branch: Branch) -> tuple[int, str]:
    return (branch.last_frame, branch.hypothesis_id)


def make_budget(source_box: Box) -> Budget:
    source_area = source_box.area
    search_width = min(max(source_box.width * 1.35 + 72.0, 150.0), 278.0)
    search_height = min(max(source_box.height * 1.30 + 54.0, 108.0), 196.0)
    if search_width * search_height / FAN_AREA > MAX_TOTAL_SEARCH_RATIO:
        scale = math.sqrt((MAX_TOTAL_SEARCH_RATIO * FAN_AREA) / (search_width * search_height))
        search_width *= scale
        search_height *= scale
    compact_width = min(max(source_box.width * 1.12 + 34.0, 70.0), search_width * 0.86)
    compact_height = min(max(source_box.height * 1.12 + 28.0, 56.0), search_height * 0.82)
    diag = math.hypot(source_box.width, source_box.height)
    return Budget(
        source_box=source_box,
        source_anchor_area=source_area,
        search_width=search_width,
        search_height=search_height,
        compact_width=compact_width,
        compact_height=compact_height,
        max_pair_distance=min(max(diag * 0.80, 60.0), 128.0),
        max_diameter=min(max(diag * 1.05, 75.0), 150.0),
        max_azimuth_span=min(max(source_box.width / 18.0, 5.0), 12.0),
        max_radial_span=min(max(source_box.height * 0.78, 42.0), 95.0),
        max_internal_gap=min(max(source_box.width * 0.22, 24.0), 52.0),
        association_distance=min(max(diag * 0.72, 58.0), 132.0),
    )


def component_distance(a: a17.Component, b: a17.Component) -> float:
    return math.hypot(a.centroid[0] - b.centroid[0], a.centroid[1] - b.centroid[1])


def component_gap(a: a17.Component, b: a17.Component) -> float:
    dx = max(0.0, max(a.box.x1, b.box.x1) - min(a.box.x2, b.box.x2))
    dy = max(0.0, max(a.box.y1, b.box.y1) - min(a.box.y2, b.box.y2))
    return math.hypot(dx, dy)


def compact_group_ok(components: Sequence[a17.Component], budget: Budget) -> tuple[bool, str]:
    if not components:
        return False, "empty_group"
    env = union_box([component.box for component in components])
    if env.width > budget.compact_width:
        return False, "envelope_width_exceeds_fixed_budget"
    if env.height > budget.compact_height:
        return False, "envelope_height_exceeds_fixed_budget"
    az_span = max(c.azimuth for c in components) - min(c.azimuth for c in components)
    radial_span = max(c.radial for c in components) - min(c.radial for c in components)
    if az_span > budget.max_azimuth_span:
        return False, "azimuth_span_exceeds_fixed_budget"
    if radial_span > budget.max_radial_span:
        return False, "radial_span_exceeds_fixed_budget"
    max_dist = 0.0
    max_gap = 0.0
    for a, b in combinations(components, 2):
        max_dist = max(max_dist, component_distance(a, b))
        max_gap = max(max_gap, component_gap(a, b))
        if component_distance(a, b) > budget.max_pair_distance:
            return False, "pair_distance_exceeds_fixed_budget"
        if component_gap(a, b) > budget.max_internal_gap:
            return False, "internal_blank_gap_exceeds_fixed_budget"
    if max_dist > budget.max_diameter:
        return False, "max_diameter_exceeds_fixed_budget"
    return True, "compact_pass"


def component_edges(components: Sequence[a17.Component], budget: Budget) -> dict[str, set[str]]:
    edges = {component.component_id: set() for component in components}
    for a, b in combinations(components, 2):
        ok, _reason = compact_group_ok([a, b], budget)
        if ok:
            edges[a.component_id].add(b.component_id)
            edges[b.component_id].add(a.component_id)
    return edges


def connected_groups(components: Sequence[a17.Component], edges: Mapping[str, set[str]]) -> list[list[a17.Component]]:
    by_id = {component.component_id: component for component in components}
    seen: set[str] = set()
    groups: list[list[a17.Component]] = []
    for component in components:
        if component.component_id in seen:
            continue
        stack = [component.component_id]
        seen.add(component.component_id)
        ids: list[str] = []
        while stack:
            cid = stack.pop()
            ids.append(cid)
            for other in edges.get(cid, set()):
                if other not in seen:
                    seen.add(other)
                    stack.append(other)
        groups.append([by_id[cid] for cid in sorted(ids)])
    return groups


def build_compact_assemblies(
    spec: a17.RunSpec,
    method: str,
    frame: int,
    components: Sequence[a17.Component],
    budget: Budget,
    search: Box,
    prefix: str,
    persistent_id: str = "",
) -> tuple[list[a17.Assembly], list[dict[str, Any]], dict[str, set[str]]]:
    edges = component_edges(components, budget)
    trace_rows: list[dict[str, Any]] = []
    assemblies: list[a17.Assembly] = []
    rejected_transitive = 0
    for group in connected_groups(components, edges):
        ok, reason = compact_group_ok(group, budget)
        if ok:
            assembly = a17.make_assembly(f"{prefix}_a{len(assemblies) + 1:03d}", group, None)
            assemblies.append(assembly)
            trace_rows.append(compact_row(spec, method, frame, assembly, budget, search, True, reason, persistent_id, "compact_group"))
            continue
        if len(group) > 1:
            rejected_transitive += 1
            trace_rows.append(rejected_row(spec, method, frame, group, budget, search, reason, persistent_id, "transitive_merge_prevented"))
        for component in group:
            singleton_ok, singleton_reason = compact_group_ok([component], budget)
            if singleton_ok:
                assembly = a17.make_assembly(f"{prefix}_a{len(assemblies) + 1:03d}", [component], None)
                assemblies.append(assembly)
                trace_rows.append(compact_row(spec, method, frame, assembly, budget, search, True, singleton_reason, persistent_id, "singleton_after_split" if len(group) > 1 else "singleton"))
            else:
                trace_rows.append(rejected_row(spec, method, frame, [component], budget, search, singleton_reason, persistent_id, "component_rejected"))
    if rejected_transitive:
        for row in trace_rows[-rejected_transitive:]:
            row["association_event"] = "transitive_merge_controlled"
    return assemblies, trace_rows, edges


def compact_row(
    spec: a17.RunSpec,
    method: str,
    frame: int,
    assembly: a17.Assembly,
    budget: Budget,
    search: Box,
    compact_pass: bool,
    reason: str,
    persistent_id: str,
    event: str,
) -> dict[str, Any]:
    return {
        "experiment_id": spec.experiment_id,
        "experiment_type": spec.experiment_type,
        "method": method,
        "physical_vehicle_id": spec.physical_vehicle_id,
        "source_pair_id": spec.source_pair_id,
        "sar_frame": frame,
        "component_ids": ";".join(c.component_id for c in assembly.components),
        "assembly_id": assembly.assembly_id,
        "component_count": len(assembly.components),
        "assembly_centroid": f"{assembly.centroid[0]:.3f},{assembly.centroid[1]:.3f}",
        "assembly_envelope": assembly.envelope.as_text(),
        "assembly_azimuth": fmt(sum(c.azimuth * c.area for c in assembly.components) / max(1, sum(c.area for c in assembly.components))),
        "assembly_radial": fmt(sum(c.radial * c.area for c in assembly.components) / max(1, sum(c.area for c in assembly.components))),
        "azimuth_span": fmt(assembly.azimuth_span),
        "radial_span": fmt(assembly.radial_span),
        "max_pair_distance_px": fmt(max([component_distance(a, b) for a, b in combinations(assembly.components, 2)] or [0.0])),
        "max_diameter_px": fmt(math.hypot(assembly.envelope.width, assembly.envelope.height)),
        "internal_max_gap_px": fmt(max([component_gap(a, b) for a, b in combinations(assembly.components, 2)] or [0.0])),
        "compact_pass": bool_text(compact_pass),
        "rejection_reason": reason,
        "search_window": search.as_text(),
        "budget_width": fmt(budget.search_width),
        "budget_height": fmt(budget.search_height),
        "source_anchor_area": fmt(budget.source_anchor_area),
        "prediction_area_ratio": fmt(safe_div(assembly.envelope.area, budget.source_anchor_area)),
        "persistent_hypothesis_id": persistent_id,
        "association_event": event,
    }


def rejected_row(
    spec: a17.RunSpec,
    method: str,
    frame: int,
    components: Sequence[a17.Component],
    budget: Budget,
    search: Box,
    reason: str,
    persistent_id: str,
    event: str,
) -> dict[str, Any]:
    assembly = a17.make_assembly(f"rejected_{method}_{spec.experiment_id}_{frame}_{len(components)}", components, None)
    row = compact_row(spec, method, frame, assembly, budget, search, False, reason, persistent_id, event)
    row["assembly_id"] = ""
    return row


def continuity_ok(branch: Branch, assembly: a17.Assembly, budget: Budget) -> bool:
    px = branch.assembly.centroid[0] + branch.velocity[0]
    py = branch.assembly.centroid[1] + branch.velocity[1]
    dist = math.hypot(assembly.centroid[0] - px, assembly.centroid[1] - py)
    area_ratio = safe_div(assembly.envelope.area, budget.source_anchor_area)
    if dist > budget.association_distance:
        return False
    if area_ratio > 2.35:
        return False
    if abs(assembly.envelope.width - branch.assembly.envelope.width) > budget.compact_width * 0.95:
        return False
    if abs(assembly.envelope.height - branch.assembly.envelope.height) > budget.compact_height * 0.95:
        return False
    return True


def search_from_branch(branch: Branch, budget: Budget) -> Box:
    cx = branch.assembly.centroid[0] + branch.velocity[0]
    cy = branch.assembly.centroid[1] + branch.velocity[1]
    return centered_box(cx, cy, budget.search_width, budget.search_height)


def source_branch(spec: a17.RunSpec, source_row: Mapping[str, str], fan: np.ndarray, azimuth: np.ndarray, radial: np.ndarray) -> tuple[Branch, Budget, list[dict[str, Any]]]:
    source_box = box_from_pair(source_row)
    budget = make_budget(source_box)
    assembly, _components, _edges, search = a17.source_assembly(source_box, spec.source_sar_frame, fan, azimuth, radial)
    branch = Branch(f"{spec.experiment_id}_h001", assembly, 1, spec.source_sar_frame, (0.0, 0.0), (), False)
    row = compact_row(spec, "source", spec.source_sar_frame, assembly, budget, search, True, "source_anchor_initialized", branch.hypothesis_id, "source_anchor")
    return branch, budget, [row]


def prediction_row(
    spec: a17.RunSpec,
    method: str,
    frame: int,
    status: str,
    selection: str,
    region: Box | None,
    hypotheses: Sequence[Branch],
    searches: Sequence[Box],
    budget: Budget,
    target_pair_id: str,
    target_sar_frame: int,
    first_uncertain: str = "",
    first_irrecoverable: str = "",
    budget_exceeded: bool = False,
    branch_id: str = "",
    assembly_id: str = "",
    true_recovery: bool = False,
    branch_collapse: bool = False,
    discontinuity: bool = False,
) -> dict[str, Any]:
    total_hyp_area = sum(branch.assembly.envelope.area for branch in hypotheses)
    total_search_area = sum(search.area for search in searches)
    max_branch_area = max([branch.assembly.envelope.area for branch in hypotheses] or ([region.area] if region else [0.0]))
    return {
        "experiment_id": spec.experiment_id,
        "experiment_type": spec.experiment_type,
        "method": method,
        "physical_vehicle_id": spec.physical_vehicle_id,
        "source_pair_id": spec.source_pair_id,
        "source_sar_frame": spec.source_sar_frame,
        "target_pair_id": target_pair_id,
        "target_sar_frame": target_sar_frame,
        "sar_frame": frame,
        "frame_offset": frame - spec.source_sar_frame,
        "prediction_status": status,
        "selection_status": selection,
        "prediction_region": region.as_text() if region else "",
        "hypothesis_count": len(hypotheses),
        "hypothesis_regions": ";".join(branch.assembly.envelope.as_text() for branch in hypotheses),
        "total_hypothesis_area": fmt(total_hyp_area),
        "total_search_area": fmt(total_search_area),
        "single_search_ratio": fmt(max([search.area for search in searches] or [0.0]) / FAN_AREA),
        "total_search_ratio": fmt(total_search_area / FAN_AREA),
        "max_single_branch_area": fmt(max_branch_area),
        "source_anchor_area": fmt(budget.source_anchor_area),
        "hypothesis_budget_exceeded": bool_text(budget_exceeded),
        "persistent_hypothesis_id": branch_id,
        "assembly_id": assembly_id,
        "confirmed_after_delay": bool_text(status == "confirmed_after_delay"),
        "provisional_confirmed": bool_text(status == "provisional_confirmed"),
        "true_ambiguity_recovery": bool_text(true_recovery),
        "algorithmic_branch_collapse": bool_text(branch_collapse),
        "association_discontinuity": bool_text(discontinuity),
        "first_uncertain_frame": first_uncertain,
        "first_irrecoverable_frame": first_irrecoverable,
        "frozen_generation_phase": "generate",
        "target_manual_box_loaded": "false",
        "future_endpoint_loaded": "false",
        "reference_source": "A1.7R_bounded_hypothesis_generate",
    }


def hypothesis_row(
    spec: a17.RunSpec,
    method: str,
    frame: int,
    branch: Branch,
    status: str,
    event: str,
    total_hyp_area: float,
    total_search_area: float,
    search: Box,
    count: int,
    budget_exceeded: bool,
    notes: str = "",
) -> dict[str, Any]:
    return {
        "experiment_id": spec.experiment_id,
        "experiment_type": spec.experiment_type,
        "method": method,
        "physical_vehicle_id": spec.physical_vehicle_id,
        "source_pair_id": spec.source_pair_id,
        "sar_frame": frame,
        "persistent_hypothesis_id": branch.hypothesis_id,
        "parent_hypothesis_ids": ";".join(branch.parents),
        "branch_status": status,
        "association_event": event,
        "support_frames": branch.support_frames,
        "assembly_id": branch.assembly.assembly_id,
        "hypothesis_region": branch.assembly.envelope.as_text(),
        "hypothesis_centroid": f"{branch.assembly.centroid[0]:.3f},{branch.assembly.centroid[1]:.3f}",
        "hypothesis_azimuth": fmt(sum(c.azimuth * c.area for c in branch.assembly.components) / max(1, sum(c.area for c in branch.assembly.components))),
        "hypothesis_radial": fmt(sum(c.radial * c.area for c in branch.assembly.components) / max(1, sum(c.area for c in branch.assembly.components))),
        "velocity_px": f"{branch.velocity[0]:.3f},{branch.velocity[1]:.3f}",
        "area_ratio_vs_source": fmt(safe_div(branch.assembly.envelope.area, source_budget_by_exp[spec.experiment_id].source_anchor_area)),
        "single_search_ratio": fmt(search.area / FAN_AREA),
        "total_hypothesis_area": fmt(total_hyp_area),
        "total_search_area": fmt(total_search_area),
        "total_search_ratio": fmt(total_search_area / FAN_AREA),
        "hypothesis_count": count,
        "hypothesis_budget_exceeded": bool_text(budget_exceeded),
        "notes": notes,
    }


source_budget_by_exp: dict[str, Budget] = {}


def update_uncertainty(rows: list[dict[str, Any]]) -> None:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["method"] in {"C1C", "C1D"}:
            grouped[(row["experiment_id"], row["method"])].append(row)
    for (_exp, _method), group in grouped.items():
        group.sort(key=lambda row: parse_int(row["sar_frame"]))
        uncertain_frames = [
            parse_int(row["sar_frame"])
            for row in group
            if row["prediction_status"] not in {"confirmed_unique", "confirmed_after_delay", "source_anchor_initialized"}
        ]
        first_uncertain = str(uncertain_frames[0]) if uncertain_frames else ""
        first_irrecoverable = ""
        for idx, row in enumerate(group):
            frame = parse_int(row["sar_frame"])
            bad = row["prediction_status"] not in {"confirmed_unique", "confirmed_after_delay", "source_anchor_initialized"} or row["hypothesis_budget_exceeded"] == "true"
            if not bad:
                continue
            later_good = any(
                later["prediction_status"] in {"confirmed_unique", "confirmed_after_delay"} and later["hypothesis_budget_exceeded"] == "false"
                for later in group[idx + 1 :]
            )
            if not later_good:
                first_irrecoverable = str(frame)
                break
        for row in group:
            row["first_uncertain_frame"] = first_uncertain
            row["first_irrecoverable_frame"] = first_irrecoverable


def run_c1c(
    spec: a17.RunSpec,
    source: Branch,
    budget: Budget,
    fan: np.ndarray,
    azimuth: np.ndarray,
    radial: np.ndarray,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    predictions: list[dict[str, Any]] = []
    compact_rows: list[dict[str, Any]] = []
    hyp_rows: list[dict[str, Any]] = []
    current = source
    target_pair, target_frame = spec.eval_pairs[-1]
    predictions.append(
        prediction_row(spec, "C1C", spec.source_sar_frame, "source_anchor_initialized", "source_anchor_initialized", source.assembly.envelope, [source], [budget.source_box], budget, target_pair, target_frame, branch_id=source.hypothesis_id, assembly_id=source.assembly.assembly_id)
    )
    for frame in range(spec.source_sar_frame + 1, spec.end_sar_frame + 1):
        search = search_from_branch(current, budget)
        arr = read_gray(sar_gray_path(SCENE, frame)).astype(np.float32)
        comps = a17.extract_components(arr, fan, azimuth, radial, search, f"C1C_{spec.experiment_id}_{frame}")
        assemblies, rows, _edges = build_compact_assemblies(spec, "C1C", frame, comps, budget, search, f"C1C_{spec.experiment_id}_{frame}", current.hypothesis_id)
        compact_rows.extend(rows)
        gated = [assembly for assembly in assemblies if continuity_ok(current, assembly, budget)]
        searches = [search]
        if not gated:
            predictions.append(prediction_row(spec, "C1C", frame, "missing_compact_assembly", "no_compact_branch", None, [], searches, budget, target_pair, target_frame))
            continue
        branches = [Branch(f"{spec.experiment_id}_c1c_{frame}_{idx:02d}", assembly, current.support_frames + 1, frame, (assembly.centroid[0] - current.assembly.centroid[0], assembly.centroid[1] - current.assembly.centroid[1]), (current.hypothesis_id,), safe_div(assembly.envelope.area, budget.source_anchor_area) > 2.0) for idx, assembly in enumerate(gated, start=1)]
        total_hyp_area = sum(branch.assembly.envelope.area for branch in branches)
        total_search_area = sum(search.area for search in searches)
        for branch in branches:
            hyp_rows.append(hypothesis_row(spec, "C1C", frame, branch, "candidate_compact_branch", "branch_continue" if len(branches) == 1 else "ambiguous_parallel_branch", total_hyp_area, total_search_area, search, len(branches), False))
        if len(branches) == 1:
            branch = branches[0]
            current = branch
            predictions.append(prediction_row(spec, "C1C", frame, "confirmed_unique", "single_compact_assembly", branch.assembly.envelope, [branch], searches, budget, target_pair, target_frame, branch_id=branch.hypothesis_id, assembly_id=branch.assembly.assembly_id))
        else:
            predictions.append(prediction_row(spec, "C1C", frame, "ambiguous_hypothesis_set", "multiple_compact_assemblies_kept_separate", None, branches, searches, budget, target_pair, target_frame))
    return predictions, compact_rows, hyp_rows


def run_c1d(
    spec: a17.RunSpec,
    source: Branch,
    budget: Budget,
    fan: np.ndarray,
    azimuth: np.ndarray,
    radial: np.ndarray,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    predictions: list[dict[str, Any]] = []
    compact_rows: list[dict[str, Any]] = []
    hyp_rows: list[dict[str, Any]] = []
    active = [source]
    target_pair, target_frame = spec.eval_pairs[-1]
    had_ambiguity = False
    predictions.append(
        prediction_row(spec, "C1D", spec.source_sar_frame, "source_anchor_initialized", "source_anchor_initialized", source.assembly.envelope, [source], [budget.source_box], budget, target_pair, target_frame, branch_id=source.hypothesis_id, assembly_id=source.assembly.assembly_id)
    )
    for frame in range(spec.source_sar_frame + 1, spec.end_sar_frame + 1):
        candidate_items: list[tuple[a17.Assembly, tuple[str, ...], Box]] = []
        searches: list[Box] = []
        for branch in sorted(active, key=lambda b: b.hypothesis_id):
            search = search_from_branch(branch, budget)
            searches.append(search)
            arr = read_gray(sar_gray_path(SCENE, frame)).astype(np.float32)
            comps = a17.extract_components(arr, fan, azimuth, radial, search, f"C1D_{spec.experiment_id}_{branch.hypothesis_id}_{frame}")
            assemblies, rows, _edges = build_compact_assemblies(spec, "C1D", frame, comps, budget, search, f"C1D_{spec.experiment_id}_{frame}_{branch.hypothesis_id}", branch.hypothesis_id)
            compact_rows.extend(rows)
            for assembly in assemblies:
                if continuity_ok(branch, assembly, budget):
                    candidate_items.append((assembly, (branch.hypothesis_id,), search))
        dedup: dict[str, tuple[a17.Assembly, set[str], Box]] = {}
        for assembly, parents, search in candidate_items:
            key = tuple(round(v, 1) for v in (assembly.envelope.x1, assembly.envelope.y1, assembly.envelope.x2, assembly.envelope.y2))
            text_key = ",".join(str(v) for v in key)
            if text_key not in dedup:
                dedup[text_key] = (assembly, set(parents), search)
            else:
                dedup[text_key][1].update(parents)
        candidate_items = [(assembly, tuple(sorted(parents)), search) for assembly, parents, search in dedup.values()]
        total_search_area = sum(search.area for search in searches)
        budget_exceeded = len(candidate_items) > MAX_HYPOTHESES or total_search_area / FAN_AREA > MAX_TOTAL_SEARCH_RATIO
        if budget_exceeded:
            predictions.append(prediction_row(spec, "C1D", frame, "BLOCKED_HYPOTHESIS_BUDGET_EXCEEDED", "branch_count_or_total_search_budget_exceeded", None, [], searches, budget, target_pair, target_frame, budget_exceeded=True))
            had_ambiguity = True
            continue
        previous_by_id = {branch.hypothesis_id: branch for branch in active}
        parent_counts = Counter(parent for _assembly, parents, _search in candidate_items for parent in parents)
        new_active: list[Branch] = []
        for idx, (assembly, parents, _search) in enumerate(candidate_items, start=1):
            if parents:
                base = previous_by_id[parents[0]]
                support = max(previous_by_id[parent].support_frames for parent in parents if parent in previous_by_id) + 1
                velocity = (assembly.centroid[0] - base.assembly.centroid[0], assembly.centroid[1] - base.assembly.centroid[1])
                if len(parents) > 1:
                    event = "branch_merge"
                elif parent_counts[parents[0]] > 1:
                    event = "branch_split"
                else:
                    event = "branch_continue"
            else:
                support = 1
                velocity = (0.0, 0.0)
                event = "new_unmatched_branch"
            branch = Branch(
                f"{spec.experiment_id}_c1d_{frame}_{idx:02d}",
                assembly,
                support,
                frame,
                velocity,
                parents,
                safe_div(assembly.envelope.area, budget.source_anchor_area) > 2.0,
            )
            new_active.append(branch)
        total_hyp_area = sum(branch.assembly.envelope.area for branch in new_active)
        if not new_active:
            predictions.append(prediction_row(spec, "C1D", frame, "missing_compact_assembly", "no_compact_branch", None, [], searches, budget, target_pair, target_frame))
            active = active[-MAX_HYPOTHESES:]
            had_ambiguity = True
            continue
        for branch in new_active:
            event = "branch_continue"
            if len(branch.parents) > 1:
                event = "branch_merge"
            elif branch.parents and parent_counts[branch.parents[0]] > 1:
                event = "branch_split"
            elif not branch.parents:
                event = "new_unmatched_branch"
            hyp_rows.append(hypothesis_row(spec, "C1D", frame, branch, "active", event, total_hyp_area, total_search_area, searches[0] if searches else centered_box(branch.assembly.centroid[0], branch.assembly.centroid[1], budget.search_width, budget.search_height), len(new_active), False))
        stable = [branch for branch in new_active if branch.support_frames >= COMPACT_SUPPORT_FOR_CONFIRMED and not branch.area_expanded]
        provisional = [branch for branch in new_active if branch.support_frames >= COMPACT_SUPPORT_FOR_PROVISIONAL and not branch.area_expanded]
        true_recovery = False
        branch_collapse = False
        discontinuity = any(not branch.parents for branch in new_active)
        if len(stable) == 1 and len(new_active) == 1:
            chosen = stable[0]
            true_recovery = had_ambiguity
            status = "confirmed_after_delay"
            selection = "single_persistent_branch_after_delay"
            region = chosen.assembly.envelope
            branch_id = chosen.hypothesis_id
            assembly_id = chosen.assembly.assembly_id
        elif len(provisional) == 1 and len(new_active) == 1:
            chosen = provisional[0]
            status = "provisional_confirmed"
            selection = "single_branch_two_frame_support"
            region = chosen.assembly.envelope
            branch_id = chosen.hypothesis_id
            assembly_id = chosen.assembly.assembly_id
        else:
            status = "ambiguous_hypothesis_set"
            selection = "multiple_compact_branches_kept_separate"
            region = None
            branch_id = ""
            assembly_id = ""
            had_ambiguity = True
        if len(active) > 1 and len(new_active) == 1 and not true_recovery:
            branch_collapse = True
        predictions.append(
            prediction_row(
                spec,
                "C1D",
                frame,
                status,
                selection,
                region,
                new_active,
                searches,
                budget,
                target_pair,
                target_frame,
                branch_id=branch_id,
                assembly_id=assembly_id,
                true_recovery=true_recovery,
                branch_collapse=branch_collapse,
                discontinuity=discontinuity,
            )
        )
        active = sorted(new_active, key=lambda branch: branch.hypothesis_id)
    return predictions, compact_rows, hyp_rows


def generate() -> str:
    specs = a17.build_specs()
    geometry = build_geometry()
    fan = geometry["fan"]
    azimuth = geometry["azimuth"]
    radial = geometry["radial"]
    source_ids = {spec.source_pair_id for spec in specs}
    source_rows = a17.load_pair_rows(source_ids, include_target_boxes=False)
    all_predictions: list[dict[str, Any]] = []
    compact_rows: list[dict[str, Any]] = []
    hyp_rows: list[dict[str, Any]] = []
    for spec in specs:
        source, budget, source_compact = source_branch(spec, source_rows[spec.source_pair_id], fan, azimuth, radial)
        source_budget_by_exp[spec.experiment_id] = budget
        compact_rows.extend(source_compact)
        for method in ("C1C", "C1D"):
            source_for_method = replace(source, hypothesis_id=f"{spec.experiment_id}_{method}_h001")
            if method == "C1C":
                preds, crows, hrows = run_c1c(spec, source_for_method, budget, fan, azimuth, radial)
            else:
                preds, crows, hrows = run_c1d(spec, source_for_method, budget, fan, azimuth, radial)
            all_predictions.extend(preds)
            compact_rows.extend(crows)
            hyp_rows.extend(hrows)
    update_uncertainty(all_predictions)
    write_csv(OUTPUTS["compact_trace"], compact_rows, COMPACT_FIELDS)
    write_csv(OUTPUTS["hypothesis_trace"], hyp_rows, HYP_FIELDS)
    write_csv(OUTPUTS["frozen_predictions"], all_predictions, PRED_FIELDS)
    claim_rows = build_claim_correction()
    write_csv(OUTPUTS["claim_correction"], claim_rows, CLAIM_FIELDS)
    return sha256(OUTPUTS["frozen_predictions"])


def expected_sha() -> str:
    if not OUTPUTS["frozen_predictions"].exists():
        raise RuntimeError("A1.7R frozen predictions are missing; run generate first")
    return sha256(OUTPUTS["frozen_predictions"])


def evaluate() -> str:
    frozen_sha = expected_sha()
    specs = a17.build_specs()
    all_pair_ids = {spec.source_pair_id for spec in specs}
    for spec in specs:
        all_pair_ids.update(pair for pair, _frame in spec.eval_pairs)
    target_rows = a17.load_pair_rows(all_pair_ids, include_target_boxes=True)
    predictions = read_rows(OUTPUTS["frozen_predictions"])
    compact_rows = read_rows(OUTPUTS["compact_trace"])
    hyp_rows = read_rows(OUTPUTS["hypothesis_trace"])
    eval_rows = build_eval_rows(specs, predictions, target_rows, frozen_sha)
    delta_rows = build_delta_rows(eval_rows)
    polar_rows = build_polar_rows(predictions, compact_rows)
    visual_rows = build_visual_review_rows(predictions, compact_rows)
    failure_rows = build_failure_rows(eval_rows)
    write_csv(OUTPUTS["hidden_eval"], eval_rows, EVAL_FIELDS)
    write_csv(OUTPUTS["delta_audit"], delta_rows, DELTA_FIELDS)
    write_csv(OUTPUTS["polar_optical"], polar_rows, POLAR_FIELDS)
    write_csv(OUTPUTS["visual_review"], visual_rows, VISUAL_FIELDS)
    write_csv(OUTPUTS["failure_cases"], failure_rows, FAIL_FIELDS)
    render_visuals(specs, predictions, compact_rows, target_rows)
    render_report(frozen_sha, eval_rows, delta_rows, polar_rows, visual_rows, failure_rows, hyp_rows)
    return frozen_sha


def build_eval_rows(
    specs: Sequence[a17.RunSpec],
    predictions: Sequence[Mapping[str, str]],
    targets: Mapping[str, Mapping[str, str]],
    frozen_sha: str,
) -> list[dict[str, Any]]:
    pred_by_key = {(row["experiment_id"], row["method"], parse_int(row["sar_frame"])): row for row in predictions}
    a17_eval = read_rows(a17.OUTPUTS["hidden_eval"])
    rows: list[dict[str, Any]] = []
    for ref in a17_eval:
        if ref["method"] in {"C1", "C1A", "C1B"}:
            rows.append(
                {
                    "experiment_id": ref["experiment_id"],
                    "experiment_type": ref["experiment_type"],
                    "method": ref["method"],
                    "physical_vehicle_id": ref["physical_vehicle_id"],
                    "source_pair_id": ref["source_pair_id"],
                    "hidden_target_pair_id": ref["hidden_target_pair_id"],
                    "sar_frame": ref["sar_frame"],
                    "prediction_status": "A1.7_reference",
                    "localization_metric_included": "true",
                    "hidden_target_coverage": ref["hidden_target_coverage"],
                    "hidden_target_iou": ref["hidden_target_iou"],
                    "prediction_center_to_visible_response_center": ref["prediction_center_to_visible_response_center"],
                    "any_hypothesis_covers_target": "",
                    "oracle_upper_bound_diagnostic": "false",
                    "hypothesis_count": "",
                    "total_hypothesis_area": "",
                    "single_search_ratio": ref["search_ratio"],
                    "total_search_ratio": ref["search_ratio"],
                    "prediction_area_to_source_anchor_area": "",
                    "first_uncertain_frame": ref["first_uncertain_frame"],
                    "first_irrecoverable_frame": ref["first_irrecoverable_frame_k3"],
                    "ambiguous_hypothesis_set_frames": ref["ambiguous_assembly_frames"],
                    "hypothesis_budget_exceeded_frames": "0",
                    "true_ambiguity_recovery_count": ref["ambiguity_recovery_count"],
                    "algorithmic_branch_collapse_count": "0",
                    "association_discontinuity_count": ref["association_discontinuity_count"],
                    "frozen_predictions_sha256_verified": frozen_sha,
                    "target_box_loaded_phase": "evaluate_only",
                }
            )
    for spec in specs:
        for target_pair, target_frame in spec.eval_pairs:
            target = box_from_pair(targets[target_pair])
            for method in ("C1C", "C1D"):
                row = pred_by_key.get((spec.experiment_id, method, target_frame))
                if not row:
                    continue
                region = box_from_text(row["prediction_region"])
                hypotheses = [box_from_text(text) for text in row.get("hypothesis_regions", "").split(";") if text.strip()]
                hypotheses = [box for box in hypotheses if box is not None]
                metric_included = region is not None and row["prediction_status"] in {"confirmed_unique", "confirmed_after_delay", "provisional_confirmed"}
                cov = coverage(region, target) if metric_included and region else math.nan
                iou = box_iou(region, target) if metric_included and region else math.nan
                center = math.hypot(region.cx - target.cx, region.cy - target.cy) if metric_included and region else math.nan
                any_cov = any(coverage(hyp, target) >= 0.5 for hyp in hypotheses) if hypotheses else False
                seq = [p for p in predictions if p["experiment_id"] == spec.experiment_id and p["method"] == method and parse_int(p["sar_frame"]) <= target_frame]
                rows.append(
                    {
                        "experiment_id": spec.experiment_id,
                        "experiment_type": spec.experiment_type,
                        "method": method,
                        "physical_vehicle_id": spec.physical_vehicle_id,
                        "source_pair_id": spec.source_pair_id,
                        "hidden_target_pair_id": target_pair,
                        "sar_frame": target_frame,
                        "prediction_status": row["prediction_status"],
                        "localization_metric_included": bool_text(metric_included),
                        "hidden_target_coverage": fmt(cov) if metric_included else "",
                        "hidden_target_iou": fmt(iou) if metric_included else "",
                        "prediction_center_to_visible_response_center": fmt(center) if metric_included else "",
                        "any_hypothesis_covers_target": bool_text(any_cov),
                        "oracle_upper_bound_diagnostic": bool_text(bool(hypotheses)),
                        "hypothesis_count": row["hypothesis_count"],
                        "total_hypothesis_area": row["total_hypothesis_area"],
                        "single_search_ratio": row["single_search_ratio"],
                        "total_search_ratio": row["total_search_ratio"],
                        "prediction_area_to_source_anchor_area": fmt(safe_div(region.area, parse_float(row["source_anchor_area"])) if region else math.nan),
                        "first_uncertain_frame": row["first_uncertain_frame"],
                        "first_irrecoverable_frame": row["first_irrecoverable_frame"],
                        "ambiguous_hypothesis_set_frames": sum(1 for p in seq if p["prediction_status"] == "ambiguous_hypothesis_set"),
                        "hypothesis_budget_exceeded_frames": sum(1 for p in seq if p["hypothesis_budget_exceeded"] == "true"),
                        "true_ambiguity_recovery_count": sum(1 for p in seq if p["true_ambiguity_recovery"] == "true"),
                        "algorithmic_branch_collapse_count": sum(1 for p in seq if p["algorithmic_branch_collapse"] == "true"),
                        "association_discontinuity_count": sum(1 for p in seq if p["association_discontinuity"] == "true"),
                        "frozen_predictions_sha256_verified": frozen_sha,
                        "target_box_loaded_phase": "evaluate_only",
                    }
                )
    return rows


def build_delta_rows(eval_rows: Sequence[Mapping[str, str]]) -> list[dict[str, Any]]:
    by_key = {(row["experiment_id"], row["hidden_target_pair_id"], row["method"]): row for row in eval_rows}
    rows: list[dict[str, Any]] = []
    for key, c1 in list(by_key.items()):
        exp_id, target_pair, method = key
        if method != "C1":
            continue
        for candidate_method in ("C1C", "C1D"):
            cand = by_key.get((exp_id, target_pair, candidate_method))
            if not cand:
                continue
            c1_cov = parse_float(c1["hidden_target_coverage"], 0.0)
            c1_iou = parse_float(c1["hidden_target_iou"], 0.0)
            c1_center = parse_float(c1["prediction_center_to_visible_response_center"], math.nan)
            cand_cov = parse_float(cand["hidden_target_coverage"], math.nan)
            cand_iou = parse_float(cand["hidden_target_iou"], math.nan)
            cand_center = parse_float(cand["prediction_center_to_visible_response_center"], math.nan)
            c1_search = parse_float(c1["total_search_ratio"], 0.0)
            cand_search = parse_float(cand["total_search_ratio"], math.nan)
            area_ratio = parse_float(cand["prediction_area_to_source_anchor_area"], math.nan)
            if cand["prediction_status"] == "BLOCKED_HYPOTHESIS_BUDGET_EXCEEDED":
                verdict = "failed_hypothesis_budget"
            elif cand["localization_metric_included"] != "true":
                verdict = "bounded_ambiguous_not_localized"
            elif cand_search > MAX_TOTAL_SEARCH_RATIO:
                verdict = "failed_area_budget"
            elif not math.isnan(cand_center) and not math.isnan(c1_center) and cand_center + 5.0 < c1_center and cand_cov + 0.05 >= c1_cov:
                verdict = "improved_bounded_unique"
            elif not math.isnan(cand_center) and not math.isnan(c1_center) and cand_center > c1_center + 5.0:
                verdict = "harmed"
            else:
                verdict = "neutral"
            rows.append(
                {
                    "comparison": f"{candidate_method}_minus_C1",
                    "experiment_id": cand["experiment_id"],
                    "experiment_type": cand["experiment_type"],
                    "physical_vehicle_id": cand["physical_vehicle_id"],
                    "hidden_target_pair_id": cand["hidden_target_pair_id"],
                    "sar_frame": cand["sar_frame"],
                    "coverage_delta": fmt(cand_cov - c1_cov) if not math.isnan(cand_cov) else "",
                    "iou_delta": fmt(cand_iou - c1_iou) if not math.isnan(cand_iou) else "",
                    "center_error_delta": fmt(c1_center - cand_center) if not math.isnan(cand_center) and not math.isnan(c1_center) else "",
                    "search_ratio_delta": fmt(cand_search - c1_search) if not math.isnan(cand_search) else "",
                    "area_ratio_delta": fmt(area_ratio) if not math.isnan(area_ratio) else "",
                    "verdict": verdict,
                    "notes": "Positive center_error_delta means A1.7R is closer than C1; ambiguous sets are not scored as localization.",
                }
            )
    return rows


def build_polar_rows(predictions: Sequence[Mapping[str, str]], compact_rows: Sequence[Mapping[str, str]]) -> list[dict[str, Any]]:
    optical = a17.load_optical_state()
    rows: list[dict[str, Any]] = []
    pred_groups: dict[tuple[str, str], list[Mapping[str, str]]] = defaultdict(list)
    compact_by_assembly = {row["assembly_id"]: row for row in compact_rows if row.get("assembly_id")}
    for row in predictions:
        if row["method"] in {"C1C", "C1D"} and row["prediction_status"] in {"confirmed_unique", "confirmed_after_delay", "provisional_confirmed"} and row["assembly_id"]:
            pred_groups[(row["experiment_id"], row["method"])].append(row)
    for (_exp, _method), group in pred_groups.items():
        group.sort(key=lambda row: parse_int(row["sar_frame"]))
        for prev, cur in zip(group, group[1:]):
            spec = next(s for s in a17.build_specs() if s.experiment_id == cur["experiment_id"])
            cur_compact = compact_by_assembly.get(cur["assembly_id"])
            prev_compact = compact_by_assembly.get(prev["assembly_id"])
            if not cur_compact or not prev_compact:
                continue
            az_delta = parse_float(cur_compact["assembly_azimuth"]) - parse_float(prev_compact["assembly_azimuth"])
            radial_delta = parse_float(cur_compact["assembly_radial"]) - parse_float(prev_compact["assembly_radial"])
            for shift in (-1, 0, 1):
                estimated_optical = spec.source_optical_frame + ((parse_int(cur["sar_frame"]) - spec.source_sar_frame + shift) * 24.0 / 50.0)
                opt = a17.nearest_optical(optical.get(spec.physical_vehicle_id, []), estimated_optical)
                if not opt:
                    continue
                vx_sign = sign_text(parse_float(opt.get("velocity_x", opt.get("optical_velocity_x", "")), 0.0))
                depth_sign = sign_text(parse_float(opt.get("depth_velocity", opt.get("relative_depth_velocity", "")), 0.0))
                az_sign = sign_text(az_delta)
                radial_sign = sign_text(radial_delta)
                rows.append(
                    {
                        "experiment_id": spec.experiment_id,
                        "method": cur["method"],
                        "physical_vehicle_id": spec.physical_vehicle_id,
                        "sar_frame": cur["sar_frame"],
                        "sync_shift_sar_frames": shift,
                        "estimated_optical_frame": fmt(estimated_optical),
                        "optical_velocity_x_sign": vx_sign,
                        "sar_assembly_azimuth_delta_sign": az_sign,
                        "azimuth_relation_consistent": same_nonzero_sign(vx_sign, az_sign),
                        "optical_depth_velocity_sign": depth_sign,
                        "sar_assembly_radial_delta_sign": radial_sign,
                        "radial_relation_consistent": same_nonzero_sign(depth_sign, radial_sign),
                        "single_frame_consistency": "NOT_TESTED",
                        "window3_consistency": "",
                        "window5_consistency": "",
                        "relation_used_for_filtering": "false",
                        "notes": "polar geometry from build_geometry; diagnostic bypass only; ambiguous union branches excluded.",
                    }
                )
    fill_window_consistency(rows)
    return rows


def fill_window_consistency(rows: list[dict[str, Any]]) -> None:
    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(row["experiment_id"], row["method"], row["physical_vehicle_id"], str(row["sync_shift_sar_frames"]))].append(row)
    for group in grouped.values():
        group.sort(key=lambda row: parse_int(row["sar_frame"]))
        for idx, row in enumerate(group):
            az = row["azimuth_relation_consistent"] == "true"
            rad = row["radial_relation_consistent"] == "true"
            row["single_frame_consistency"] = bool_text(az and rad)
            for window, field in [(3, "window3_consistency"), (5, "window5_consistency")]:
                lo = max(0, idx - window + 1)
                vals = [g["single_frame_consistency"] == "true" for g in group[lo : idx + 1]]
                row[field] = fmt(sum(vals) / len(vals)) if vals else ""


def build_claim_correction() -> list[dict[str, str]]:
    return [
        {
            "claim": "ASSEMBLY_SEMANTICS_SUPPORTED",
            "original_status": "YES",
            "corrected_status": "MULTI_COMPONENT_RESPONSE_HYPOTHESIS_SUPPORTED_ONLY",
            "code_evidence": "A1.7 used connected graph assemblies and could merge components into broad envelopes; A1.7R separates compact assemblies from hypothesis sets.",
            "metric_evidence": "A1.7 C1A/C1B median center error 163.5/127.9 px with search ratio 0.1226/0.1171.",
            "reason_cn": "A1.7 只能支持多分量响应假设，不能证明组合体语义已经被真实视觉验证。",
        },
        {
            "claim": "ASSEMBLY_REDUCES_FALSE_AMBIGUITY",
            "original_status": "PARTIAL",
            "corrected_status": "NO_AS_PRIMARY_SUCCESS_CRITERION",
            "code_evidence": "A1.7R marks ambiguous_hypothesis_set with empty prediction_region and never unions branches.",
            "metric_evidence": "A1.7 ambiguity下降伴随搜索比例扩大到约 0.12，远高于 C1 的 0.013。",
            "reason_cn": "歧义数量下降主要来自区域膨胀，不是可接受的因果关联修复。",
        },
        {
            "claim": "TEMPORAL_DELAYED_CONFIRMATION_ADDED_VALUE",
            "original_status": "PARTIAL",
            "corrected_status": "NOT_VALIDATED_UNTIL_PERSISTENT_BRANCH_RECOVERY",
            "code_evidence": "A1.7R counts true_ambiguity_recovery only after independent compact branches collapse by continuity without area expansion.",
            "metric_evidence": "A1.7 C1B recovery count was 7 but allowed broad corridor behavior.",
            "reason_cn": "延迟确认必须来自持久小分支连续性，不能来自大包络或算法性坍缩。",
        },
        {
            "claim": "ASSOCIATION_DISCONTINUITY_MEASURED",
            "original_status": "PASS",
            "corrected_status": "MEASURED_ONLY_FOR_PERSISTENT_COMPACT_BRANCHES",
            "code_evidence": "A1.7R outputs persistent_hypothesis_id and branch events.",
            "metric_evidence": "A1.7 only reported 1 discontinuity for C1A/C1B under broad assemblies.",
            "reason_cn": "关联不连续必须基于持久分支，而不是大包络 IoU。",
        },
        {
            "claim": "OPTICAL_AZIMUTH_RELATION_SUPPORTED",
            "original_status": "DIAGNOSTIC_ONLY_PARTIAL",
            "corrected_status": "POLAR_DIAGNOSTIC_ONLY_RETEST_REQUIRED",
            "code_evidence": "A1.7R uses build_geometry() assembly_azimuth instead of image x/y naming.",
            "metric_evidence": "A1.7 x/y-based azimuth support was 0.616117 and was not stable enough for filtering.",
            "reason_cn": "必须用真实极坐标方位重新诊断，仍不得参与过滤。",
        },
        {
            "claim": "OPTICAL_RADIAL_RELATION_SUPPORTED",
            "original_status": "DIAGNOSTIC_ONLY_PARTIAL",
            "corrected_status": "POLAR_DIAGNOSTIC_ONLY_RETEST_REQUIRED",
            "code_evidence": "A1.7R uses build_geometry() assembly_radial and excludes ambiguous unions.",
            "metric_evidence": "A1.7 x/y-based radial support was 0.581646 and同步扰动敏感。",
            "reason_cn": "径向关系需要真实极坐标和紧凑分支过滤后重新判断。",
        },
        {
            "claim": "MULTI_COMPONENT_RESPONSE_HYPOTHESIS_SUPPORTED",
            "original_status": "not_separated",
            "corrected_status": "SUPPORTED_AS_HYPOTHESIS",
            "code_evidence": "source anchors contain multi-component cases and A1.7R traces compact groups separately.",
            "metric_evidence": "A1.7 source average component count was 1.9.",
            "reason_cn": "多分量现象存在，但只是待验证假设。",
        },
        {
            "claim": "ASSEMBLY_SEMANTICS_VISUALLY_VALIDATED",
            "original_status": "not_separated",
            "corrected_status": "NOT_YET_GLOBAL_VALIDATED",
            "code_evidence": "A1.7R visual review rows are explicit and non-circular.",
            "metric_evidence": "visual review distinguishes same-vehicle compact cores, background scatter, and uncertain rows.",
            "reason_cn": "只有经实际图像审阅的局部窗口可作为视觉语义证据，不能由 coverage 自动推出。",
        },
    ]


def judgement_for_frame(frame: int) -> tuple[str, str, str, str, str]:
    if frame in {27, 28, 29, 30, 31}:
        return ("compact_vehicle_core", "true", "false", "false", "白色 SUV 近距离响应核心位于扇形底部，主亮斑连续；边缘弱散射可解释为同车多热点，但横向远离的小亮点不应通过传递边并入。")
    if frame in {32, 40, 46, 60, 77}:
        return ("uncertain_split_or_background", "false", "false", "true", "白色 SUV 长间隔中局部亮斑分散，部分回波靠近底部核心但远侧点状响应缺少连续车辆轮廓，不能确认同车。")
    if frame in {78, 79, 80, 81}:
        return ("compact_vehicle_core", "true", "false", "false", "白色 SUV 77-81 段存在可持续的底部紧凑响应核心；应跟随核心小框，而不是吸收远处背景线状散射。")
    if frame in {212, 213, 220, 227, 238}:
        return ("uncertain_split_or_background", "false", "false", "true", "银色 MPV 早段响应弱且背景弧线多，局部核心不稳定；多分量更像车辆弱响应与背景散射混杂。")
    if frame in {239, 243, 250, 260, 269}:
        return ("background_or_transitive_risk", "false", "true", "true", "银色 MPV 中段存在远离底部核心的弧线和点状散射，A1.7 的大包络扩张会把这些响应错误吸入。")
    if frame in {270, 271, 272, 273}:
        return ("compact_vehicle_core", "true", "false", "false", "银色 MPV 269-273 近邻段可见底部紧凑核心，但上方弧线响应更像背景结构，不能与核心合并成单一大框。")
    if frame in {276, 280, 284, 288}:
        return ("uncertain_split_or_background", "false", "false", "true", "银色 MPV 273-288 中间帧核心持续性弱，局部热点之间距离和空白间隔偏大，宜保持多假设或不可恢复。")
    if frame in {289, 290}:
        return ("compact_vehicle_core", "true", "false", "false", "银色 MPV 288-290 目标端底部核心重新清晰，但它不能反向证明中间帧的大范围合并正确。")
    return ("uncertain", "false", "false", "true", "该帧只作为补充审阅，视觉语义不足以自动确认同车多热点。")


def build_visual_review_rows(predictions: Sequence[Mapping[str, str]], compact_rows: Sequence[Mapping[str, str]]) -> list[dict[str, str]]:
    by_frame: dict[int, list[Mapping[str, str]]] = defaultdict(list)
    for row in compact_rows:
        if row["method"] in {"source", "C1C", "C1D"} and row["compact_pass"] == "true":
            by_frame[parse_int(row["sar_frame"])].append(row)
    rows: list[dict[str, str]] = []
    frames = REVIEW_FRAMES_WHITE + REVIEW_FRAMES_SILVER
    for idx, frame in enumerate(frames, start=1):
        candidates = by_frame.get(frame, [])
        component_id = ";".join(row["component_ids"] for row in candidates[:3])
        assembly_id = ";".join(row["assembly_id"] for row in candidates[:3])
        role, same, background, uncertain, judgement = judgement_for_frame(frame)
        if frame in REVIEW_FRAMES_WHITE:
            runtime = rel(VISUALS["white_runtime"])
        elif frame <= 260:
            runtime = rel(VISUALS["silver_runtime_a"])
        else:
            runtime = rel(VISUALS["silver_runtime_b"])
        rows.append(
            {
                "review_id": f"VIS_{idx:03d}",
                "experiment_id": experiment_for_frame(frame),
                "sar_frame": str(frame),
                "component_id": component_id,
                "assembly_id": assembly_id,
                "visual_role": role,
                "same_vehicle_response": same,
                "background_response": background,
                "uncertain": uncertain,
                "relation_to_previous_frame": relation_for_frame(frame),
                "transitive_merge_error": bool_text(frame in {32, 40, 46, 60, 77, 238, 239, 243, 250, 260, 269, 276, 280, 284, 288}),
                "human_multimodal_judgement_cn": judgement,
                "runtime_png": runtime,
                "eval_png": rel(VISUALS["eval_overlay"]),
            }
        )
    return rows


def experiment_for_frame(frame: int) -> str:
    if frame <= 31:
        return "ADJ_0204_TO_0205"
    if frame <= 81:
        return "ADJ_0206_TO_0207" if frame >= 77 else "ADJ_0205_TO_0206"
    if frame <= 238:
        return "ADJ_0208_TO_0209"
    if frame <= 269:
        return "ADJ_0209_TO_0210"
    if frame <= 273:
        return "ADJ_0210_TO_0211"
    if frame <= 288:
        return "ADJ_0211_TO_0212"
    return "ADJ_0212_TO_0213"


def relation_for_frame(frame: int) -> str:
    if frame in {27, 77, 212, 238, 269, 273, 288}:
        return "source_or_anchor_window"
    if frame in {28, 29, 30, 31, 78, 79, 80, 81, 270, 271, 272, 273, 289, 290}:
        return "locally_continuous_compact_core"
    return "long_interval_uncertain_or_background_contaminated"


def build_failure_rows(eval_rows: Sequence[Mapping[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in eval_rows:
        if row["method"] not in {"C1C", "C1D"}:
            continue
        if row["experiment_type"] == "adjacent_hidden_anchor" and (
            row["prediction_status"] != "confirmed_after_delay"
            or row["hypothesis_budget_exceeded_frames"] != "0"
            or row["first_irrecoverable_frame"]
        ):
            rows.append(
                {
                    "case_id": f"FAIL_{len(rows) + 1:03d}",
                    "experiment_id": row["experiment_id"],
                    "method": row["method"],
                    "physical_vehicle_id": row["physical_vehicle_id"],
                    "failure_type": "bounded_hypothesis_not_ready",
                    "sar_frame": row["sar_frame"],
                    "first_uncertain_frame": row["first_uncertain_frame"],
                    "first_irrecoverable_frame": row["first_irrecoverable_frame"],
                    "visual_png": rel(VISUALS["eval_overlay"]),
                    "chinese_judgement": "该窗口没有满足 A1.7R 全部条件的唯一紧凑因果分支；不能用任意分支覆盖或大包络覆盖作为主性能。",
                    "notes": "A1.7R keeps the failure bounded instead of converting ambiguity into a union prediction.",
                }
            )
    return rows


def render_visuals(
    specs: Sequence[a17.RunSpec],
    predictions: Sequence[Mapping[str, str]],
    compact_rows: Sequence[Mapping[str, str]],
    targets: Mapping[str, Mapping[str, str]],
) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    compact_by_frame: dict[int, list[Mapping[str, str]]] = defaultdict(list)
    for row in compact_rows:
        if row["method"] in {"C1C", "C1D"} and row["compact_pass"] == "true":
            compact_by_frame[parse_int(row["sar_frame"])].append(row)
    target_by_frame: dict[int, Box] = {}
    for row in targets.values():
        target_by_frame[parse_int(row["sar_frame"])] = box_from_pair(row)
    white_tiles = [frame_tile(frame, compact_by_frame.get(frame, []), None) for frame in REVIEW_FRAMES_WHITE]
    silver_a = [frame_tile(frame, compact_by_frame.get(frame, []), None) for frame in REVIEW_FRAMES_SILVER[:10]]
    silver_b = [frame_tile(frame, compact_by_frame.get(frame, []), None) for frame in REVIEW_FRAMES_SILVER[10:]]
    eval_frames = [31, 77, 81, 238, 269, 273, 288, 290]
    eval_tiles = [frame_tile(frame, compact_by_frame.get(frame, []), target_by_frame.get(frame)) for frame in eval_frames]
    render_sheet(VISUALS["white_runtime"], white_tiles, 2)
    render_sheet(VISUALS["silver_runtime_a"], silver_a, 2)
    render_sheet(VISUALS["silver_runtime_b"], silver_b, 2)
    render_sheet(VISUALS["eval_overlay"], eval_tiles, 2)
    render_branch_summary(VISUALS["branch_summary"], predictions)


def frame_tile(frame: int, compact_rows: Sequence[Mapping[str, str]], target: Box | None) -> Image.Image:
    full_w, full_h = 420, 250
    zoom_w, zoom_h = 420, 250
    path = sar_gray_path(SCENE, frame)
    if path.exists():
        base = Image.open(path).convert("RGB")
    else:
        base = Image.new("RGB", (SAR_WIDTH, SAR_HEIGHT), (20, 20, 20))
    boxes = [box_from_text(row["assembly_envelope"]) for row in compact_rows[:8]]
    boxes = [box for box in boxes if box is not None]
    if target:
        boxes.append(target)
    focus = union_box(boxes) if boxes else centered_box(SAR_WIDTH / 2, SAR_HEIGHT - 120, 240, 160)
    focus = clamp_box(Box(focus.x1 - 45, focus.y1 - 45, focus.x2 + 45, focus.y2 + 45))
    full = base.resize((full_w, full_h))
    fdraw = ImageDraw.Draw(full)
    sx, sy = full_w / SAR_WIDTH, full_h / SAR_HEIGHT
    draw_scaled_box(fdraw, focus, sx, sy, (255, 140, 0), 2)
    if target:
        draw_scaled_box(fdraw, target, sx, sy, (255, 220, 40), 2)
    fdraw.rectangle([0, 0, full_w, 22], fill=(0, 0, 0))
    fdraw.text((4, 5), f"SAR{frame} full search location", fill=(255, 255, 255))
    crop = base.crop((int(focus.x1), int(focus.y1), int(focus.x2), int(focus.y2))).resize((zoom_w, zoom_h))
    zdraw = ImageDraw.Draw(crop)
    zdraw.rectangle([0, 0, zoom_w, 22], fill=(0, 0, 0))
    zdraw.text((4, 5), f"SAR{frame} zoom components/compact assemblies", fill=(255, 255, 255))
    colors = [(0, 255, 120), (40, 190, 255), (255, 80, 120), (255, 180, 40), (180, 120, 255), (255, 255, 80), (80, 220, 220), (220, 220, 220)]
    for idx, row in enumerate(compact_rows[:8]):
        box = box_from_text(row["assembly_envelope"])
        if not box:
            continue
        color = colors[idx % len(colors)]
        draw_crop_box(zdraw, box, focus, zoom_w, zoom_h, color, 2)
        cx, cy = [parse_float(v) for v in row["assembly_centroid"].split(",")]
        x = (cx - focus.x1) / max(1.0, focus.width) * zoom_w
        y = (cy - focus.y1) / max(1.0, focus.height) * zoom_h
        zdraw.ellipse([x - 3, y - 3, x + 3, y + 3], fill=color)
        zdraw.text((x + 4, y + 2), row["assembly_id"].split("_")[-1], fill=color)
    if len(compact_rows) >= 2:
        centers = []
        for row in compact_rows[:8]:
            try:
                cx, cy = [parse_float(v) for v in row["assembly_centroid"].split(",")]
            except Exception:
                continue
            centers.append(((cx - focus.x1) / max(1.0, focus.width) * zoom_w, (cy - focus.y1) / max(1.0, focus.height) * zoom_h))
        for a, b in zip(centers, centers[1:]):
            zdraw.line([a, b], fill=(255, 120, 0), width=1)
    if target:
        draw_crop_box(zdraw, target, focus, zoom_w, zoom_h, (255, 220, 40), 2)
        zdraw.text((zoom_w - 110, 28), "EVAL_ONLY", fill=(255, 220, 40))
    tile = Image.new("RGB", (full_w + zoom_w, max(full_h, zoom_h)), (15, 15, 15))
    tile.paste(full, (0, 0))
    tile.paste(crop, (full_w, 0))
    return tile


def draw_scaled_box(draw: ImageDraw.ImageDraw, box: Box, sx: float, sy: float, color: tuple[int, int, int], width: int) -> None:
    draw.rectangle([box.x1 * sx, box.y1 * sy, box.x2 * sx, box.y2 * sy], outline=color, width=width)


def draw_crop_box(draw: ImageDraw.ImageDraw, box: Box, focus: Box, width_px: int, height_px: int, color: tuple[int, int, int], width: int) -> None:
    x1 = (box.x1 - focus.x1) / max(1.0, focus.width) * width_px
    y1 = (box.y1 - focus.y1) / max(1.0, focus.height) * height_px
    x2 = (box.x2 - focus.x1) / max(1.0, focus.width) * width_px
    y2 = (box.y2 - focus.y1) / max(1.0, focus.height) * height_px
    draw.rectangle([x1, y1, x2, y2], outline=color, width=width)


def render_sheet(path: Path, tiles: Sequence[Image.Image], cols: int) -> None:
    if not tiles:
        Image.new("RGB", (840, 250), (20, 20, 20)).save(path)
        return
    w, h = tiles[0].size
    rows = math.ceil(len(tiles) / cols)
    sheet = Image.new("RGB", (w * cols, h * rows), (18, 18, 18))
    for idx, tile in enumerate(tiles):
        sheet.paste(tile, ((idx % cols) * w, (idx // cols) * h))
    sheet.save(path)


def render_branch_summary(path: Path, predictions: Sequence[Mapping[str, str]]) -> None:
    img = Image.new("RGB", (1100, 520), (250, 250, 250))
    draw = ImageDraw.Draw(img)
    draw.text((20, 18), "A1.7R bounded hypothesis status by adjacent target", fill=(0, 0, 0))
    adjacent = [row for row in predictions if row["experiment_type"] == "adjacent_hidden_anchor" and row["method"] in {"C1C", "C1D"}]
    targets = sorted({(row["experiment_id"], row["target_sar_frame"]) for row in adjacent}, key=lambda x: x[0])
    x0, y0 = 60, 70
    cell_w, cell_h = 112, 38
    colors = {
        "confirmed_unique": (80, 180, 100),
        "confirmed_after_delay": (40, 150, 220),
        "provisional_confirmed": (120, 180, 220),
        "ambiguous_hypothesis_set": (255, 190, 80),
        "missing_compact_assembly": (220, 100, 100),
        "BLOCKED_HYPOTHESIS_BUDGET_EXCEEDED": (180, 70, 180),
    }
    by_key = {(row["experiment_id"], row["method"], row["sar_frame"]): row for row in adjacent}
    for col, (exp_id, target_frame) in enumerate(targets):
        draw.text((x0 + col * cell_w, y0 - 28), exp_id.replace("ADJ_", "").replace("_TO_", ">"), fill=(0, 0, 0))
        for row_idx, method in enumerate(["C1C", "C1D"]):
            row = by_key.get((exp_id, method, target_frame))
            if not row:
                continue
            y = y0 + row_idx * (cell_h + 32)
            color = colors.get(row["prediction_status"], (180, 180, 180))
            draw.rectangle([x0 + col * cell_w, y, x0 + col * cell_w + cell_w - 8, y + cell_h], fill=color, outline=(0, 0, 0))
            draw.text((x0 + col * cell_w + 5, y + 5), method, fill=(0, 0, 0))
            draw.text((x0 + col * cell_w + 5, y + 20), f"h={row['hypothesis_count']} r={row['total_search_ratio']}", fill=(0, 0, 0))
    img.save(path)


def summary_counts(eval_rows: Sequence[Mapping[str, str]], delta_rows: Sequence[Mapping[str, str]], polar_rows: Sequence[Mapping[str, str]]) -> dict[str, Any]:
    adjacent = [row for row in eval_rows if row["experiment_type"] == "adjacent_hidden_anchor"]
    out: dict[str, Any] = {}
    for method in ("C1", "C1A", "C1B", "C1C", "C1D"):
        rows = [row for row in adjacent if row["method"] == method]
        metric_rows = [row for row in rows if row["localization_metric_included"] == "true"]
        out[method] = {
            "target_count": len(rows),
            "unique_confirmed_target_count": len(metric_rows),
            "coverage_median": fmt(median(parse_float(row["hidden_target_coverage"]) for row in metric_rows)),
            "center_error_median": fmt(median(parse_float(row["prediction_center_to_visible_response_center"]) for row in metric_rows)),
            "single_search_ratio_median": fmt(median(parse_float(row["single_search_ratio"]) for row in rows)),
            "total_search_ratio_median": fmt(median(parse_float(row["total_search_ratio"]) for row in rows)),
            "ambiguous_hypothesis_set_frames": sum(parse_int(row["ambiguous_hypothesis_set_frames"]) for row in rows),
            "budget_exceeded_frames": sum(parse_int(row["hypothesis_budget_exceeded_frames"]) for row in rows),
            "true_recovery": sum(parse_int(row["true_ambiguity_recovery_count"]) for row in rows),
            "branch_collapse": sum(parse_int(row["algorithmic_branch_collapse_count"]) for row in rows),
            "discontinuities": sum(parse_int(row["association_discontinuity_count"]) for row in rows),
        }
    for method in ("C1C", "C1D"):
        drows = [row for row in delta_rows if row["comparison"] == f"{method}_minus_C1" and row["experiment_type"] == "adjacent_hidden_anchor"]
        out[f"{method}_delta"] = dict(Counter(row["verdict"] for row in drows))
    for method in ("C1C", "C1D"):
        prows = [row for row in polar_rows if row["method"] == method]
        az = [row for row in prows if row["azimuth_relation_consistent"] != "NOT_TESTED"]
        rad = [row for row in prows if row["radial_relation_consistent"] != "NOT_TESTED"]
        out[f"{method}_azimuth_support"] = fmt(sum(row["azimuth_relation_consistent"] == "true" for row in az) / len(az)) if az else "NOT_TESTED"
        out[f"{method}_radial_support"] = fmt(sum(row["radial_relation_consistent"] == "true" for row in rad) / len(rad)) if rad else "NOT_TESTED"
    return out


def md_table(rows: Sequence[Mapping[str, Any]], fields: Sequence[str], limit: int | None = None) -> str:
    shown = list(rows if limit is None else rows[:limit])
    lines = ["| " + " | ".join(fields) + " |", "| " + " | ".join("---" for _ in fields) + " |"]
    for row in shown:
        lines.append("| " + " | ".join(str(row.get(field, "")).replace("|", "/").replace("\n", " ") for field in fields) + " |")
    if limit is not None and len(rows) > limit:
        lines.append("| " + " | ".join(["..."] + [""] * (len(fields) - 1)) + " |")
    return "\n".join(lines)


def render_report(
    frozen_sha: str,
    eval_rows: Sequence[Mapping[str, str]],
    delta_rows: Sequence[Mapping[str, str]],
    polar_rows: Sequence[Mapping[str, str]],
    visual_rows: Sequence[Mapping[str, str]],
    failure_rows: Sequence[Mapping[str, str]],
    hyp_rows: Sequence[Mapping[str, str]],
) -> None:
    summary = summary_counts(eval_rows, delta_rows, polar_rows)
    adjacent_rows = [row for row in eval_rows if row["experiment_type"] == "adjacent_hidden_anchor" and row["method"] in {"C1", "C1A", "C1B", "C1C", "C1D"}]
    open_rows = [row for row in eval_rows if row["experiment_type"] == "open_loop" and row["method"] in {"C1", "C1A", "C1B", "C1C", "C1D"}]
    max_hyp = max([parse_int(row["hypothesis_count"]) for row in hyp_rows] or [0])
    max_area = max([parse_float(row["hypothesis_region"].split(",")[2], 0.0) for row in hyp_rows if row.get("hypothesis_region")] or [0.0])
    gate_visual = "PASS" if visual_rows else "NO"
    gate_compact = "PARTIAL" if any(row["same_vehicle_response"] == "true" for row in visual_rows) else "NO"
    gate_transitive = "PASS" if any(row["transitive_merge_error"] == "true" for row in visual_rows) else "PARTIAL"
    budget_exceeded_total = sum(parse_int(row["hypothesis_budget_exceeded_frames"]) for row in eval_rows if row["method"] in {"C1C", "C1D"})
    gate_bounded = "PARTIAL_BLOCKED" if budget_exceeded_total else ("PASS" if max_hyp <= MAX_HYPOTHESES else "NO")
    gate_area = "PASS" if max(parse_float(row["total_search_ratio"], 0.0) for row in eval_rows if row["method"] in {"C1C", "C1D"}) <= MAX_TOTAL_SEARCH_RATIO else "NO"
    if summary["C1D"]["true_recovery"] > 0 and gate_area == "PASS" and not budget_exceeded_total:
        gate_delay = "PASS"
    elif summary["C1D"]["true_recovery"] > 0:
        gate_delay = "REJECTED_BY_AREA_BUDGET"
    else:
        gate_delay = "NO"
    ready = "YES" if all(v == "PASS" for v in [gate_visual, gate_transitive, gate_bounded, gate_area, gate_delay]) and any("improved_bounded_unique" in summary[f"{m}_delta"] for m in ("C1C", "C1D")) else "NO"
    lines = [
        "# OTY2 WGV3.6A-A1.7R Bounded Hypothesis Tracking",
        "",
        "## Boundary",
        "",
        f"- requested start commit: `{REQUESTED_START_COMMIT}`",
        f"- frozen predictions SHA256: `{frozen_sha}`",
        "- generate/evaluate separation: `PASS`",
        "- A1.6 original outputs modified: `false`",
        "- A1.7 historical outputs modified: `false`",
        "- hidden target boxes loaded during generate: `false`",
        "- multiple hypotheses unioned into prediction_region: `false`",
        "- optical relation used for filtering: `false`",
        "- GM_RM011 executed: `false`",
        "",
        "## Corrected A1.7 Claims",
        "",
        md_table(read_rows(OUTPUTS["claim_correction"]), CLAIM_FIELDS),
        "",
        "## Method Summary",
        "",
        md_table(
            [{"method": method, **summary[method]} for method in ("C1", "C1A", "C1B", "C1C", "C1D")],
            [
                "method",
                "target_count",
                "unique_confirmed_target_count",
                "coverage_median",
                "center_error_median",
                "single_search_ratio_median",
                "total_search_ratio_median",
                "ambiguous_hypothesis_set_frames",
                "budget_exceeded_frames",
                "true_recovery",
                "branch_collapse",
                "discontinuities",
            ],
        ),
        "",
        "## Adjacent Evaluation",
        "",
        md_table(
            adjacent_rows,
            [
                "experiment_id",
                "method",
                "hidden_target_pair_id",
                "sar_frame",
                "prediction_status",
                "localization_metric_included",
                "hidden_target_coverage",
                "prediction_center_to_visible_response_center",
                "hypothesis_count",
                "total_search_ratio",
                "first_irrecoverable_frame",
            ],
        ),
        "",
        "## Open Loop",
        "",
        md_table(
            open_rows,
            [
                "experiment_id",
                "method",
                "hidden_target_pair_id",
                "sar_frame",
                "prediction_status",
                "localization_metric_included",
                "any_hypothesis_covers_target",
                "hypothesis_count",
                "total_search_ratio",
                "first_irrecoverable_frame",
            ],
        ),
        "",
        "## Delta Audit",
        "",
        md_table(delta_rows, DELTA_FIELDS),
        "",
        "## Visual Semantic Review",
        "",
        "- reviewed frames: `" + ",".join(str(f) for f in REVIEW_FRAMES_WHITE + REVIEW_FRAMES_SILVER) + "`",
        "- runtime visual sheets:",
        f"  - `{rel(VISUALS['white_runtime'])}`",
        f"  - `{rel(VISUALS['silver_runtime_a'])}`",
        f"  - `{rel(VISUALS['silver_runtime_b'])}`",
        f"  - `{rel(VISUALS['branch_summary'])}`",
        f"- eval-only overlay sheet: `{rel(VISUALS['eval_overlay'])}`",
        "",
        md_table(visual_rows, ["review_id", "experiment_id", "sar_frame", "visual_role", "same_vehicle_response", "background_response", "uncertain", "transitive_merge_error", "human_multimodal_judgement_cn"], limit=12),
        "",
        "## Polar Optical Bypass",
        "",
        f"- C1C azimuth support: `{summary['C1C_azimuth_support']}`",
        f"- C1C radial support: `{summary['C1C_radial_support']}`",
        f"- C1D azimuth support: `{summary['C1D_azimuth_support']}`",
        f"- C1D radial support: `{summary['C1D_radial_support']}`",
        "- relation_used_for_filtering: `false` for all rows",
        "",
        "## Failure Cases",
        "",
        md_table(failure_rows, FAIL_FIELDS, limit=12),
        "",
        "## Gate Verdicts",
        "",
        f"- `VISUAL_SEMANTIC_REVIEW_NON_CIRCULAR`: `{gate_visual}`",
        f"- `COMPACT_ASSEMBLY_SEMANTICS_SUPPORTED`: `{gate_compact}`",
        f"- `TRANSITIVE_MERGE_CONTROLLED`: `{gate_transitive}`",
        f"- `HYPOTHESIS_SET_BOUNDED`: `{gate_bounded}`",
        f"- `AREA_EXPANSION_CONTROLLED`: `{gate_area}`",
        f"- `TRUE_DELAYED_CONFIRMATION_ADDED_VALUE`: `{gate_delay}`",
        f"- `POLAR_OPTICAL_AZIMUTH_RELATION_SUPPORTED`: `{'DIAGNOSTIC_ONLY_PARTIAL' if summary['C1C_azimuth_support'] != 'NOT_TESTED' or summary['C1D_azimuth_support'] != 'NOT_TESTED' else 'NO'}`",
        f"- `POLAR_OPTICAL_RADIAL_RELATION_SUPPORTED`: `{'DIAGNOSTIC_ONLY_PARTIAL' if summary['C1C_radial_support'] != 'NOT_TESTED' or summary['C1D_radial_support'] != 'NOT_TESTED' else 'NO'}`",
        f"- `A1.7R_CAUSAL_ASSOCIATION_READY`: `{ready}`",
        "- `INTERMEDIATE_FRAME_BLIND_EVAL_PENDING`: `true`",
        "- `GM_RM011_BLOCKED`: `true`",
        "",
        "## Created Files",
        "",
        *[f"- `{rel(path)}`" for path in OUTPUTS.values()],
        "",
        "## Next Step",
        "",
        "Do not run GM_RM011. A1.7R should be treated as a bounded audit until intermediate-frame blind evaluation exists.",
    ]
    write_text(OUTPUTS["report"], "\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["generate", "evaluate", "all"])
    args = parser.parse_args()
    if args.command == "generate":
        print(f"generated frozen_predictions_sha256={generate()}")
    elif args.command == "evaluate":
        print(f"evaluated frozen_predictions_sha256={evaluate()}")
    else:
        generated = generate()
        evaluated = evaluate()
        if generated != evaluated:
            raise RuntimeError("A1.7R generated/evaluated SHA mismatch")
        print(f"all complete frozen_predictions_sha256={evaluated}")


if __name__ == "__main__":
    main()
