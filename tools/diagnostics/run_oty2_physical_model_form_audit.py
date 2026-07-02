"""Audit OTY2 physical model forms and next steps.

This script advances the OTY2 mechanism notes from a flat factor ledger toward
a two-stage model sketch:

1. optical/time/azimuth/shell/state define a SAR feasible domain;
2. SAR image and SAR temporal observations confirm scattering structure inside
   that domain.

It uses SAR GT, SAR images, and review/manual signals only as posthoc
validation or modeling inspiration. It does not construct runtime priors,
generate annotation proposals, score/rank candidates, train/tune thresholds, or
claim identity truth.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = REPO_ROOT / "reports" / "oty2"
DOCS_DIR = REPO_ROOT / "docs"
WORKSPACE_LOG_DIR = Path(r"D:\profile\research\workspace\logs")

EXPECTED_LEDGER = {
    "paired_optical_object_sar_gt": 215,
    "blocked_missing_gm011_object_stream": 195,
    "sar_only_gt": 20,
    "no_oty_iou_match": 12,
}

PROVENANCE_LABELS = [
    "runtime_safe_optical_evidence",
    "runtime_safe_temporal_evidence",
    "runtime_safe_geometry_or_vehicle_physics",
    "SAR_image_observation",
    "SAR_temporal_observation",
    "SAR_GT_posthoc_evidence",
    "manual_or_review_anchor",
    "similar_imaging_reference_only",
    "hypothesis_to_validate",
    "insufficient_or_not_supported",
]

BOUNDARY_FLAGS = {
    "posthoc_sar_gt_used": True,
    "posthoc_sar_image_content_used": True,
    "gt_or_sar_image_used_for_runtime_prior_construction": False,
    "runtime_prior_construction_used_gt": False,
    "annotation_proposal_entered": False,
    "training_or_threshold_tuning_entered": False,
    "candidate_box_scoring_output": False,
    "selector_or_ranking_used": False,
    "identity_truth_claimed": False,
    "model_weights_committed": False,
    "matlab_zip_or_any_zip_committed": False,
    "detection_dropout_rows_mixed_into_clean_paired": False,
    "gm011_missing_object_stream_rows_mixed_into_correspondence": False,
    "sar_only_rows_mixed_into_optical_sar_correspondence": False,
}

MODEL_FORM_FIELDS = [
    "model_form",
    "stage_structure",
    "mathematical_sketch",
    "factor_roles",
    "supported_by_current_data",
    "current_readiness",
    "why_weighted_sum_is_insufficient",
    "evidence_summary",
    "runtime_boundary",
    "next_step",
    "provenance_labels",
]

FEASIBLE_DOMAIN_FIELDS = [
    "factor",
    "stage_role",
    "constraint_type",
    "feasible_domain_definition",
    "evidence_summary",
    "state_dependency",
    "runtime_safe_inputs",
    "posthoc_inputs_used_for_validation",
    "risk_or_failure_mode",
    "next_step",
    "provenance_labels",
]

STATE_FIELDS = [
    "state_condition",
    "sample_pool",
    "observed_count",
    "model_energy_form",
    "constraint_or_observation_roles",
    "evidence_summary",
    "reasonableness_judgement",
    "insufficient_data_or_risk",
    "next_action",
    "provenance_labels",
]

DYNAMIC_FIELDS = [
    "probe_id",
    "sample_pool",
    "scene",
    "object_hypothesis_id",
    "n_samples",
    "optical_frame_span",
    "sar_frame_span",
    "optical_trajectory_signal",
    "sar_gt_center_drift_signal",
    "sar_peak_or_centroid_drift_signal",
    "dropout_or_temporal_support",
    "runtime_support_region_conversion",
    "dynamic_model_need",
    "limits",
    "provenance_labels",
]

ANCHOR_FIELDS = [
    "anchor_id",
    "scene",
    "object_hypothesis_id",
    "sample_pool",
    "n_samples",
    "optical_frame_span",
    "sar_frame_span",
    "anchor_type",
    "residual_or_latent_to_estimate",
    "confidence_tier",
    "evidence_summary",
    "use_allowed",
    "use_forbidden",
    "review_requirement",
    "next_action",
    "provenance_labels",
]


def latest_path(pattern: str, base_dir: Path = REPORT_DIR) -> Path:
    paths = sorted(base_dir.glob(pattern))
    if not paths:
        raise FileNotFoundError(f"No file matched {base_dir / pattern}")
    return paths[-1]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def write_json(path: Path, data: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def safe_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def fmt(value: Any, digits: int = 4) -> str:
    number = safe_float(value)
    if number is None:
        return ""
    text = f"{number:.{digits}f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


def median_clean(values: Iterable[Any]) -> float | None:
    clean = [float(value) for value in (safe_float(item) for item in values) if value is not None]
    return float(median(clean)) if clean else None


def compact_counts(values: Iterable[Any], limit: int = 8) -> str:
    counter = Counter(str(value) for value in values if str(value) != "")
    return ";".join(f"{key}={count}" for key, count in counter.most_common(limit))


def validate_ledger(summary: Mapping[str, Any]) -> dict[str, Any]:
    ledger = dict(summary.get("sample_ledger", {}))
    counts = dict(ledger.get("category_counts", {}))
    ok = ledger.get("ledger_valid") and all(int(counts.get(key, -1)) == expected for key, expected in EXPECTED_LEDGER.items())
    if not ok:
        raise RuntimeError(f"Ledger mismatch; stop before model-form conclusions: {json.dumps(ledger, ensure_ascii=False)}")
    return ledger


def load_inputs(args: argparse.Namespace) -> dict[str, Any]:
    paths = {
        "physical_factor_summary_json": Path(args.physical_factor_summary_json) if args.physical_factor_summary_json else latest_path("oty2_physical_factor_modeling_summary_*.json"),
        "factor_taxonomy_csv": Path(args.factor_taxonomy_csv) if args.factor_taxonomy_csv else latest_path("oty2_physical_factor_evidence_taxonomy_*.csv"),
        "joint_factor_probe_csv": Path(args.joint_factor_probe_csv) if args.joint_factor_probe_csv else latest_path("oty2_joint_factor_probe_*.csv"),
        "object_ledger_csv": Path(args.object_ledger_csv) if args.object_ledger_csv else latest_path("oty2_object_level_factor_evidence_ledger_*.csv"),
        "sar_temporal_csv": Path(args.sar_temporal_csv) if args.sar_temporal_csv else latest_path("oty2_sar_temporal_observation_probe_*.csv"),
        "manual_review_csv": Path(args.manual_review_csv) if args.manual_review_csv else latest_path("oty2_manual_review_candidate_list_*.csv"),
        "stratified_summary_json": Path(args.stratified_summary_json) if args.stratified_summary_json else latest_path("oty2_gt_mechanism_stratified_validation_summary_*.json"),
        "az_shell_csv": Path(args.az_shell_csv) if args.az_shell_csv else latest_path("oty2_azimuth_vehicle_size_shell_audit_*.csv"),
    }
    with paths["physical_factor_summary_json"].open("r", encoding="utf-8") as handle:
        physical_summary = json.load(handle)
    with paths["stratified_summary_json"].open("r", encoding="utf-8") as handle:
        stratified_summary = json.load(handle)
    return {
        "paths": paths,
        "physical_summary": physical_summary,
        "stratified_summary": stratified_summary,
        "taxonomy_rows": read_csv(paths["factor_taxonomy_csv"]),
        "joint_rows": read_csv(paths["joint_factor_probe_csv"]),
        "object_rows": read_csv(paths["object_ledger_csv"]),
        "sar_temporal_rows": read_csv(paths["sar_temporal_csv"]),
        "manual_review_rows": read_csv(paths["manual_review_csv"]),
        "az_shell_rows": read_csv(paths["az_shell_csv"]),
    }


def scene_residual_rows(az_shell_rows: Sequence[Mapping[str, str]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, str]]] = defaultdict(list)
    for row in az_shell_rows:
        grouped[str(row.get("scene", ""))].append(row)
    rows: list[dict[str, Any]] = []
    for scene, items in sorted(grouped.items()):
        residual = median_clean(row.get("azimuth_error_to_center_deg") for row in items)
        shell_ratio = median_clean(row.get("size_shell_to_azimuth_width_ratio") for row in items)
        rows.append(
            {
                "scene": scene,
                "n": len(items),
                "median_azimuth_residual_deg": residual,
                "median_size_shell_ratio": shell_ratio,
                "status": "scene_residual_posthoc_only",
            }
        )
    return rows


def count_objects_with(rows: Sequence[Mapping[str, str]], predicate: Any) -> int:
    return sum(1 for row in rows if predicate(row))


def build_model_form_rows(
    physical_summary: Mapping[str, Any],
    stratified_summary: Mapping[str, Any],
    object_rows: Sequence[Mapping[str, str]],
    sar_temporal_rows: Sequence[Mapping[str, str]],
) -> list[dict[str, Any]]:
    key = physical_summary.get("key_metrics", {})
    ledger = physical_summary.get("sample_ledger", {}).get("category_counts", {})
    temporal_pass_rate = stratified_summary.get("frame_level", {}).get("temporal_window_pass_rate")
    clean_objects = count_objects_with(object_rows, lambda row: row.get("trajectory_reliability_label") == "clean_object_temporal_signal")
    drift_consistent = count_objects_with(sar_temporal_rows, lambda row: row.get("gt_center_vs_peak_drift_label") == "local_peak_drift_consistent_with_sar_gt_center_posthoc")
    return [
        {
            "model_form": "simple_weighted_sum",
            "stage_structure": "single-stage linear score",
            "mathematical_sketch": "E = w_time F_time + w_az F_az + w_shell F_shell + w_sar_image F_sar_image + ...",
            "factor_roles": "All factors become comparable score terms.",
            "supported_by_current_data": "No",
            "current_readiness": "not_recommended",
            "why_weighted_sum_is_insufficient": "It collapses feasibility constraints, SAR observations, state uncertainty, and posthoc GT validation into one number; it can over-count GM_RM017 repeated frames and hide GT leakage.",
            "evidence_summary": f"Current ledger has {ledger.get('paired_optical_object_sar_gt')} paired frames but only {stratified_summary['object_level']['n_objects']} object hypotheses; SAR stats are still GT-crop posthoc.",
            "runtime_boundary": "Would risk turning validation evidence into runtime prior or selector score.",
            "next_step": "Use only as a rejected baseline in documentation.",
            "provenance_labels": "insufficient_or_not_supported;SAR_GT_posthoc_evidence",
        },
        {
            "model_form": "two_stage_feasible_domain_plus_sar_observation",
            "stage_structure": "Stage 1 feasible domain, Stage 2 SAR confirmation",
            "mathematical_sketch": "C_o,t = C_time(o,t) intersect C_az(o,t) intersect C_shell(o,t) intersect C_state(o,t); X* = argmax_{X in C} P(I_sar | X) P(X | O)",
            "factor_roles": "F_time/F_az/F_shell/F_state constrain feasible support; F_sar_image/F_sar_temporal confirm scattering.",
            "supported_by_current_data": "Partially",
            "current_readiness": "recommended_model_sketch",
            "why_weighted_sum_is_insufficient": "A hard/semi-hard support domain and a SAR likelihood are different mathematical objects.",
            "evidence_summary": f"temporal pass={temporal_pass_rate}; tight shell={key.get('tight_shell_coverage')}; paired peak/background={key.get('paired_peak_to_background_median')}.",
            "runtime_boundary": "Feasible domain can be runtime-safe; SAR GT crop statistics are posthoc until replaced by support-region extraction.",
            "next_step": "Implement runtime support-region SAR peak/centroid extraction inside C_o,t.",
            "provenance_labels": "runtime_safe_temporal_evidence;runtime_safe_geometry_or_vehicle_physics;SAR_image_observation;SAR_temporal_observation;hypothesis_to_validate",
        },
        {
            "model_form": "state_conditioned_mixture",
            "stage_structure": "state-conditioned feasible domain and observations",
            "mathematical_sketch": "P(X | O,I) = sum_s P(s | O) P(X | O,I,s); E(X,s) = E_state(s) + E(X | s)",
            "factor_roles": "complete, edge/truncated, far-small, dropout, duplicate/handoff use different uncertainty and factor roles.",
            "supported_by_current_data": "Yes for current audit states, incomplete for far-small",
            "current_readiness": "ready_as_design_contract",
            "why_weighted_sum_is_insufficient": "A global weight treats complete and dropout rows as if the same evidence semantics apply.",
            "evidence_summary": f"status counts={stratified_summary['frame_level']['status_counts']}; dropout={ledger.get('no_oty_iou_match')}; clean temporal objects={clean_objects}.",
            "runtime_boundary": "State labels may guide uncertainty; manual/review state anchors are audit labels, not runtime truth.",
            "next_step": "Define state-conditioned constraint/observation table before any runtime scoring.",
            "provenance_labels": "runtime_safe_optical_evidence;runtime_safe_temporal_evidence;manual_or_review_anchor;hypothesis_to_validate",
        },
        {
            "model_form": "product_of_experts_factor_graph",
            "stage_structure": "probability factors with non-linear roles",
            "mathematical_sketch": "P(X | O,I) proportional to P_time(X|O) P_az(X|O) P_shell(X) P_sar_image(I|X) P_sar_temporal(X_1:T) P_state(s|O)",
            "factor_roles": "Feasibility experts prune or penalize impossible states; SAR image experts measure evidence inside the support region.",
            "supported_by_current_data": "Partially",
            "current_readiness": "next_step_after_support_region_extraction",
            "why_weighted_sum_is_insufficient": "Multiplicative factors can express near-zero feasibility outside time/azimuth/shell support without forcing SAR evidence to compensate.",
            "evidence_summary": f"SAR temporal object rows={len([row for row in sar_temporal_rows if row.get('sample_pool') == 'paired_optical_object_sar_gt'])}; GT-crop drift consistent rows={drift_consistent}.",
            "runtime_boundary": "P_sar_image must be computed from optical-derived support regions, not GT boxes.",
            "next_step": "Turn GT-crop SAR statistics into support-region SAR observation descriptors.",
            "provenance_labels": "SAR_image_observation;SAR_temporal_observation;hypothesis_to_validate",
        },
        {
            "model_form": "hierarchical_scene_object_residual_model",
            "stage_structure": "scene/object latent residuals",
            "mathematical_sketch": "r_s,o,t = alpha_s + beta_s h_o,t + gamma_s bottom_y_o,t + u_o + eps_o,t; beta_s ~ N(beta_0, sigma_beta^2)",
            "factor_roles": "Scene bias and object residuals explain why GM_RM017 results should not become global laws.",
            "supported_by_current_data": "No, current data are too imbalanced",
            "current_readiness": "design_only",
            "why_weighted_sum_is_insufficient": "Flat weights cannot separate scene-level bias from object-level repeated-frame effects.",
            "evidence_summary": f"paired scene counts={json.dumps(stratified_summary['scene_counts_paired'], ensure_ascii=False)}; object hypotheses={stratified_summary['object_level']['n_objects']}.",
            "runtime_boundary": "Scene/object residuals are posthoc modeling hypotheses until GM_RM019 review and GM_RM011 recovery improve balance.",
            "next_step": "GM_RM019 optical review first for existing scene balance; GM_RM011 object-stream recovery for expansion.",
            "provenance_labels": "SAR_GT_posthoc_evidence;manual_or_review_anchor;insufficient_or_not_supported",
        },
        {
            "model_form": "dynamic_dual_sequence_model",
            "stage_structure": "optical object tracklet to SAR target temporal tube",
            "mathematical_sketch": "X_tau+1 = A X_tau + B u_tau + eps_tau; O_t ~ P(O_t | X_tau(t)); I_sar_tau ~ P(I_sar_tau | X_tau)",
            "factor_roles": "Optical trajectory constrains expected SAR tube; SAR image/time confirms local scattering continuity.",
            "supported_by_current_data": "Partially",
            "current_readiness": "posthoc_probe_ready_runtime_conversion_needed",
            "why_weighted_sum_is_insufficient": "Temporal continuity is a path constraint, not an independent frame score.",
            "evidence_summary": f"object reliability={json.dumps(stratified_summary['temporal_summary']['trajectory_reliability_counts'], ensure_ascii=False)}; dropout temporal support=12/12.",
            "runtime_boundary": "Current SAR peak drift is GT-crop posthoc; runtime must use support-region peak drift.",
            "next_step": "Compute SAR peak/centroid continuity in C_o,1:T.",
            "provenance_labels": "runtime_safe_temporal_evidence;SAR_temporal_observation;SAR_GT_posthoc_evidence;hypothesis_to_validate",
        },
        {
            "model_form": "multi_object_graph_matching",
            "stage_structure": "global assignment between optical object hypotheses and SAR scattering tubes",
            "mathematical_sketch": "min_z sum_{o,r} c(o,r) z_o,r + conflict_terms; sum_r z_o,r <= 1; sum_o z_o,r <= 1",
            "factor_roles": "Time, azimuth, shell, SAR image, SAR temporal, and trajectory consistency form assignment costs after SAR tubes exist.",
            "supported_by_current_data": "Needed for GM_RM019, not implementable yet",
            "current_readiness": "conceptual_next_after_sar_tube_extraction",
            "why_weighted_sum_is_insufficient": "Duplicate/handoff and multiple boxes are global consistency problems, not independent per-frame scores.",
            "evidence_summary": "GM_RM019 has sparse paired objects, partial/edge states, duplicate/handoff risk, and 6 dropout/no-match rows.",
            "runtime_boundary": "No selector/ranking is built here; graph matching is a future global explanation form.",
            "next_step": "Use GM_RM019 review to define ambiguous object-hypothesis cases before implementing assignment.",
            "provenance_labels": "manual_or_review_anchor;runtime_safe_optical_evidence;hypothesis_to_validate",
        },
        {
            "model_form": "anchor_residual_propagation",
            "stage_structure": "high-confidence samples estimate latent residuals, not labels",
            "mathematical_sketch": "theta_o,t = g_theta(O_o,t) + Delta theta_s + delta_o + eps_o,t; Delta theta_s = median(theta_GT - g_theta(O))",
            "factor_roles": "Anchors estimate scene/object residuals for uncertainty calibration, not label copying.",
            "supported_by_current_data": "Review-gated only",
            "current_readiness": "candidate_list_only",
            "why_weighted_sum_is_insufficient": "A score cannot distinguish anchor calibration from label propagation.",
            "evidence_summary": "GM_RM017 has many rows but state-mixed; GM_RM019 has cleaner-looking objects but sparse/low azimuth coverage.",
            "runtime_boundary": "Anchors use posthoc GT for diagnosis only; no labels are propagated into runtime priors.",
            "next_step": "Create anchor candidate list and require review before residual propagation.",
            "provenance_labels": "SAR_GT_posthoc_evidence;manual_or_review_anchor;hypothesis_to_validate",
        },
    ]


def build_feasible_domain_rows(physical_summary: Mapping[str, Any], stratified_summary: Mapping[str, Any]) -> list[dict[str, Any]]:
    key = physical_summary.get("key_metrics", {})
    ledger = physical_summary.get("sample_ledger", {}).get("category_counts", {})
    return [
        {
            "factor": "C_time / F_time",
            "stage_role": "feasible_domain",
            "constraint_type": "semi-hard constraint",
            "feasible_domain_definition": "SAR frame tau in [(50/24)t + Delta_s - eps_t, (50/24)t + Delta_s + eps_t]; use temporal tube, not optical_frame * 2.",
            "evidence_summary": "temporal window pass=0.9953; dropout temporal_continuation=12/12.",
            "state_dependency": "dropout and truncation widen reliance on temporal tube; complete frames use it as synchronization support.",
            "runtime_safe_inputs": "optical frame index, acquisition fps 24/50, optical object tracklet, jitter margin.",
            "posthoc_inputs_used_for_validation": "SAR GT frame membership in window.",
            "risk_or_failure_mode": "Treating software sync as hardware timestamp truth or using optical_frame*2.",
            "next_step": "Keep as support-domain contract; quantify jitter sensitivity per state.",
            "provenance_labels": "runtime_safe_temporal_evidence;SAR_GT_posthoc_evidence",
        },
        {
            "factor": "C_az / F_az",
            "stage_role": "feasible_domain",
            "constraint_type": "semi-hard constraint",
            "feasible_domain_definition": "theta in [g_theta(O_o,t)-m(s), g_theta(O_o,t)+m(s)] with state-conditioned margin m(s).",
            "evidence_summary": f"original azimuth coverage={key.get('azimuth_original_coverage')}; GM_RM019 weaker than GM_RM017.",
            "state_dependency": "complete can use narrower prior; edge/duplicate/dropout need wider or review-gated uncertainty.",
            "runtime_safe_inputs": "optical object state, scene geometry, fan-polar mapping.",
            "posthoc_inputs_used_for_validation": "SAR GT azimuth residual and coverage.",
            "risk_or_failure_mode": "Selecting a margin from posthoc coverage would turn validation into runtime tuning.",
            "next_step": "Use state-conditioned margins as hypotheses; review GM_RM019 residuals.",
            "provenance_labels": "runtime_safe_geometry_or_vehicle_physics;SAR_GT_posthoc_evidence;hypothesis_to_validate",
        },
        {
            "factor": "C_shell / F_shell",
            "stage_role": "feasible_domain",
            "constraint_type": "semi-hard constraint",
            "feasible_domain_definition": "Intersect azimuth sector with plausible vehicle footprint shell: tight/base/relaxed profiles by state.",
            "evidence_summary": f"tight/base/relaxed coverage={key.get('tight_shell_coverage')}/{key.get('base_shell_coverage')}/1; tight misses remain informative.",
            "state_dependency": "complete may attempt tight/base; edge/truncated/duplicate/dropout require relaxed or partial-visible shells.",
            "runtime_safe_inputs": "vehicle physical size ranges, optical state, fan-polar geometry.",
            "posthoc_inputs_used_for_validation": "SAR GT long/short axis and shell coverage.",
            "risk_or_failure_mode": "Calling base/relaxed 100% coverage precise localization.",
            "next_step": "Keep shell as domain support, not final SAR box; inspect tight misses.",
            "provenance_labels": "runtime_safe_geometry_or_vehicle_physics;SAR_GT_posthoc_evidence",
        },
        {
            "factor": "C_state / F_state",
            "stage_role": "feasible_domain_and_uncertainty_router",
            "constraint_type": "semi-hard routing plus soft uncertainty scale",
            "feasible_domain_definition": "State s controls whether range_shape is active, shell is relaxed, and SAR temporal evidence is emphasized.",
            "evidence_summary": f"status counts={stratified_summary['frame_level']['status_counts']}; dropout pool={ledger.get('no_oty_iou_match')}.",
            "state_dependency": "This factor is itself state-conditioned: complete, edge, truncated, far-small, duplicate/handoff, dropout.",
            "runtime_safe_inputs": "optical object stream, visibility/truncation indicators, temporal continuity.",
            "posthoc_inputs_used_for_validation": "review/manual state anchors and dropout support.",
            "risk_or_failure_mode": "Using review labels as runtime truth or mixing dropout into clean morphology.",
            "next_step": "Define state table before any runtime inference.",
            "provenance_labels": "runtime_safe_optical_evidence;runtime_safe_temporal_evidence;manual_or_review_anchor",
        },
        {
            "factor": "F_range_shape",
            "stage_role": "soft optical observation or uncertainty modulator",
            "constraint_type": "soft observation, not hard constraint",
            "feasible_domain_definition": "For complete/stable objects, optical height/bottom_y/area can modulate range uncertainty; edge/dropout weaken or disable it.",
            "evidence_summary": f"height-radius pearson={key.get('range_shape_height_radius_pearson')}; area/bottom_y also strong, aspect unstable.",
            "state_dependency": "complete only as hypothesis; edge/truncated/far-small/dropout mostly uncertainty modulation.",
            "runtime_safe_inputs": "optical bbox height, bottom_y, area from object stream.",
            "posthoc_inputs_used_for_validation": "SAR GT radius correlation.",
            "risk_or_failure_mode": "Frame-level correlation becomes object-level law.",
            "next_step": "Validate on reviewed complete object segments.",
            "provenance_labels": "runtime_safe_optical_evidence;SAR_GT_posthoc_evidence;hypothesis_to_validate",
        },
        {
            "factor": "F_sar_image",
            "stage_role": "SAR observation likelihood",
            "constraint_type": "soft observation likelihood",
            "feasible_domain_definition": "P_sar_image(I|X) from local peak/background, box/background, scatter concentration, centroid residual, long/short axis, mainlobe/sidelobe diagnostics.",
            "evidence_summary": f"paired peak/background median={key.get('paired_peak_to_background_median')}; paired box/background={key.get('paired_box_to_background_median')}.",
            "state_dependency": "more important for far-small, edge, truncated, and dropout states; complete still uses it for confirmation.",
            "runtime_safe_inputs": "SAR image content inside optical-derived support region C_o,t.",
            "posthoc_inputs_used_for_validation": "Current GT-crop SAR statistics and SAR-only morphology.",
            "risk_or_failure_mode": "Using GT crop statistics as runtime prior or selector.",
            "next_step": "Implement support-region SAR peak extraction.",
            "provenance_labels": "SAR_image_observation;SAR_GT_posthoc_evidence;hypothesis_to_validate",
        },
        {
            "factor": "F_sar_temporal",
            "stage_role": "SAR temporal observation likelihood",
            "constraint_type": "soft path likelihood",
            "feasible_domain_definition": "E_sar_temporal(X_1:T) rewards temporally coherent local peak/centroid/axis support inside C_o,1:T.",
            "evidence_summary": "GT-crop local peak drift exists for paired objects; dropout SAR posthoc support=12/12.",
            "state_dependency": "dominant for dropout/truncated/edge; useful as stabilizer for complete objects.",
            "runtime_safe_inputs": "SAR image sequence inside temporal tube after feasible-domain construction.",
            "posthoc_inputs_used_for_validation": "SAR GT centers and GT-crop peak/centroid drift.",
            "risk_or_failure_mode": "Rejecting SAR temporal direction just because current probe is GT-crop; the correct fix is support-region extraction.",
            "next_step": "Track peaks/centroids in C_o,1:T, not in GT boxes.",
            "provenance_labels": "SAR_temporal_observation;SAR_image_observation;SAR_GT_posthoc_evidence;hypothesis_to_validate",
        },
        {
            "factor": "manual_review_and_SAR_GT",
            "stage_role": "posthoc_validation_and_diagnosis",
            "constraint_type": "not runtime constraint",
            "feasible_domain_definition": "Not part of C_o,t; used to validate and diagnose model forms.",
            "evidence_summary": "Manual review candidates include GM_RM019 optical continuity and GM_RM011 stream recovery needs.",
            "state_dependency": "Review is most needed for duplicate/handoff/dropout/sparse states.",
            "runtime_safe_inputs": "None for prior construction.",
            "posthoc_inputs_used_for_validation": "SAR GT, review optical boxes, manual labels.",
            "risk_or_failure_mode": "Leaking GT/review fields into runtime construction.",
            "next_step": "Keep provenance explicit in every output table.",
            "provenance_labels": "manual_or_review_anchor;SAR_GT_posthoc_evidence",
        },
    ]


def build_state_rows(stratified_summary: Mapping[str, Any], object_rows: Sequence[Mapping[str, str]]) -> list[dict[str, Any]]:
    status_counts = dict(stratified_summary.get("status_context_counts", {}))
    ledger = stratified_summary.get("sample_ledger", {}).get("category_counts", {})
    gm019_objects = [row for row in object_rows if row.get("scene") == "GM_RM019"]
    clean_objects = [row for row in object_rows if row.get("trajectory_reliability_label") == "clean_object_temporal_signal"]
    return [
        {
            "state_condition": "complete_visible",
            "sample_pool": "paired_optical_object_sar_gt",
            "observed_count": str(status_counts.get("complete", 0)),
            "model_energy_form": "E = E_az + E_shell + E_range_shape + E_sar_image",
            "constraint_or_observation_roles": "C_az and C_shell semi-hard; range_shape soft; SAR image likelihood confirms.",
            "evidence_summary": "complete rows exist but include only a few objects; tight shell misses 3 complete GM_RM017 rows.",
            "reasonableness_judgement": "reasonable_with_state_and_scene_caution",
            "insufficient_data_or_risk": "Do not treat complete frame-level correlation as object-level law.",
            "next_action": "Identify complete morphology segments in GM_RM019 review.",
            "provenance_labels": "runtime_safe_optical_evidence;runtime_safe_geometry_or_vehicle_physics;SAR_GT_posthoc_evidence;hypothesis_to_validate",
        },
        {
            "state_condition": "edge_or_truncated",
            "sample_pool": "paired plus dropout pools",
            "observed_count": str(status_counts.get("edge", 0)),
            "model_energy_form": "E = E_az + E_shell_relaxed + E_sar_temporal; range_shape as uncertainty modulation only",
            "constraint_or_observation_roles": "wider feasible domain; SAR temporal/image evidence more important.",
            "evidence_summary": "edge rows=58; dropout rows show temporal and SAR support.",
            "reasonableness_judgement": "strongly_reasonable_as_state_condition",
            "insufficient_data_or_risk": "Do not mix dropout into clean morphology statistics.",
            "next_action": "Use support-region SAR temporal extraction for edge/dropout cases.",
            "provenance_labels": "runtime_safe_temporal_evidence;SAR_temporal_observation;manual_or_review_anchor;hypothesis_to_validate",
        },
        {
            "state_condition": "far_small",
            "sample_pool": "weak_vehicle_layer / unresolved current split",
            "observed_count": "not_isolated_in_current_model_form_inputs",
            "model_energy_form": "E = E_time + E_az + E_sar_image",
            "constraint_or_observation_roles": "bbox morphology is not a strong localization factor; SAR image likelihood dominates confirmation.",
            "evidence_summary": "Current tables group many weak vehicles but do not isolate far-small for this model-form audit.",
            "reasonableness_judgement": "physically_reasonable_but_currently_insufficient",
            "insufficient_data_or_risk": "Need explicit far-small routing before estimating separate parameters.",
            "next_action": "Add far-small state split in the next object/state audit.",
            "provenance_labels": "runtime_safe_optical_evidence;SAR_image_observation;insufficient_or_not_supported",
        },
        {
            "state_condition": "dropout_or_no_match",
            "sample_pool": "detection dropout / no_oty_iou_match / temporal continuation pool",
            "observed_count": str(ledger.get("no_oty_iou_match", 0)),
            "model_energy_form": "E = E_time + E_optical_temporal + E_sar_temporal",
            "constraint_or_observation_roles": "optical temporal continuation plus SAR temporal support recover existence; no clean morphology.",
            "evidence_summary": "temporal continuation=12/12; SAR posthoc support=12/12; manual review required=12/12.",
            "reasonableness_judgement": "strong_special_pool_support",
            "insufficient_data_or_risk": "Propagation boxes are diagnostic only; not labels.",
            "next_action": "Convert to support-region SAR temporal evidence for existence confirmation.",
            "provenance_labels": "runtime_safe_temporal_evidence;SAR_temporal_observation;SAR_GT_posthoc_evidence;manual_or_review_anchor",
        },
        {
            "state_condition": "duplicate_or_handoff",
            "sample_pool": "paired optical-object/SAR-GT posthoc",
            "observed_count": str(status_counts.get("duplicate_or_handoff", 0)),
            "model_energy_form": "object_hypothesis ambiguity + graph matching review; no identity truth",
            "constraint_or_observation_roles": "global consistency and review-needed signal, not per-frame local score.",
            "evidence_summary": "duplicate/handoff rows=17, mostly state-mixed object hypotheses.",
            "reasonableness_judgement": "requires_global_or_review_model",
            "insufficient_data_or_risk": "A single-object model can pick a plausible-looking but ambiguous explanation.",
            "next_action": "Use GM_RM019 review to define ambiguous object-hypothesis examples.",
            "provenance_labels": "manual_or_review_anchor;runtime_safe_optical_evidence;hypothesis_to_validate",
        },
        {
            "state_condition": "gmrm019_complex",
            "sample_pool": "GM_RM019 paired + dropout",
            "observed_count": str(len(gm019_objects)),
            "model_energy_form": "state mixture plus possible graph matching",
            "constraint_or_observation_roles": "low azimuth coverage and sparse objects require review before generalization.",
            "evidence_summary": "GM_RM019 has 5 paired object hypotheses, 16 paired frames, and 6 dropout/no-match rows.",
            "reasonableness_judgement": "manual_review_required_before_scene_generalization",
            "insufficient_data_or_risk": "Sparse object frames can look clean while azimuth coverage remains weak.",
            "next_action": "Manual optical GT / identity-continuity review.",
            "provenance_labels": "manual_or_review_anchor;runtime_safe_optical_evidence;SAR_GT_posthoc_evidence;hypothesis_to_validate",
        },
        {
            "state_condition": "sar_only",
            "sample_pool": "sar_only_gt_reference",
            "observed_count": str(ledger.get("sar_only_gt", 0)),
            "model_energy_form": "SAR morphology reference only",
            "constraint_or_observation_roles": "can inform SAR observation vocabulary, not optical-SAR correspondence.",
            "evidence_summary": "SAR-only rows=20; local peak supported=12/20 in previous reference.",
            "reasonableness_judgement": "reasonable_as_sar_reference_only",
            "insufficient_data_or_risk": "No optical object counterpart.",
            "next_action": "Use for SAR likelihood design, not correspondence statistics.",
            "provenance_labels": "SAR_image_observation;SAR_GT_posthoc_evidence",
        },
        {
            "state_condition": "gmrm011_blocked",
            "sample_pool": "blocked_missing_gm011_object_stream",
            "observed_count": str(ledger.get("blocked_missing_gm011_object_stream", 0)),
            "model_energy_form": "blocked from object-level model until optical stream exists",
            "constraint_or_observation_roles": "not a missing annotation problem; object stream recovery input need.",
            "evidence_summary": "GM_RM011 has SAR GT/review optical linkage but no current OTY object stream for 195 rows.",
            "reasonableness_judgement": "object_stream_recovery_required",
            "insufficient_data_or_risk": "Cannot enter optical-object/SAR-GT mechanism modeling yet.",
            "next_action": "Run OTY0/OTY1/OTY1t object stream construction with optical data only.",
            "provenance_labels": "runtime_safe_optical_evidence;manual_or_review_anchor;hypothesis_to_validate",
        },
    ]


def build_dynamic_rows(
    object_rows: Sequence[Mapping[str, str]],
    sar_temporal_rows: Sequence[Mapping[str, str]],
) -> list[dict[str, Any]]:
    sar_by_key = {
        (row.get("scene", ""), row.get("object_hypothesis_id", "")): row
        for row in sar_temporal_rows
        if row.get("sample_pool") == "paired_optical_object_sar_gt"
    }
    rows: list[dict[str, Any]] = []
    for index, obj in enumerate(object_rows, start=1):
        key = (obj.get("scene", ""), obj.get("object_hypothesis_id", ""))
        sar = sar_by_key.get(key, {})
        n = safe_float(obj.get("n_paired_frames")) or 0
        dynamic_need = "object_level_dynamic_model_needed" if n >= 3 else "insufficient_for_dynamic_model"
        if "GM_RM019" == obj.get("scene") and (obj.get("azimuth_pass_rate") in {"0", "0.5"} or n < 4):
            dynamic_need = "dynamic_model_plus_manual_review_needed"
        rows.append(
            {
                "probe_id": f"D{index:02d}",
                "sample_pool": "paired_optical_object_sar_gt",
                "scene": obj.get("scene", ""),
                "object_hypothesis_id": obj.get("object_hypothesis_id", ""),
                "n_samples": obj.get("n_paired_frames", ""),
                "optical_frame_span": obj.get("optical_frame_span", ""),
                "sar_frame_span": obj.get("sar_frame_span", ""),
                "optical_trajectory_signal": f"area={obj.get('area_vs_radius_trend')}; height={obj.get('height_vs_radius_trend')}; bottom_y={obj.get('bottom_y_vs_radius_trend')}; center_az={obj.get('center_x_vs_azimuth_trend')}",
                "sar_gt_center_drift_signal": f"x_slope={sar.get('sar_gt_center_x_slope_per_sar_frame', '')}; y_slope={sar.get('sar_gt_center_y_slope_per_sar_frame', '')}",
                "sar_peak_or_centroid_drift_signal": sar.get("gt_center_vs_peak_drift_label", obj.get("sar_local_peak_drift_label", "")),
                "dropout_or_temporal_support": "not_dropout_pool",
                "runtime_support_region_conversion": "Replace GT-crop peak/centroid drift with peak/centroid tracking inside C_o,1:T.",
                "dynamic_model_need": dynamic_need,
                "limits": obj.get("review_need", ""),
                "provenance_labels": "runtime_safe_temporal_evidence;SAR_temporal_observation;SAR_image_observation;SAR_GT_posthoc_evidence;hypothesis_to_validate",
            }
        )
    dropout = next((row for row in sar_temporal_rows if row.get("sample_pool") == "detection_dropout_temporal_continuation"), {})
    if dropout:
        rows.append(
            {
                "probe_id": "D_dropout",
                "sample_pool": "detection_dropout_temporal_continuation",
                "scene": dropout.get("scene", ""),
                "object_hypothesis_id": "",
                "n_samples": dropout.get("n_samples", ""),
                "optical_frame_span": dropout.get("optical_frame_span", ""),
                "sar_frame_span": dropout.get("sar_frame_span", ""),
                "optical_trajectory_signal": "optical temporal continuation supports existence despite current-frame dropout",
                "sar_gt_center_drift_signal": "not_object_track_drift",
                "sar_peak_or_centroid_drift_signal": dropout.get("gt_center_vs_peak_drift_label", ""),
                "dropout_or_temporal_support": dropout.get("temporal_support_summary", ""),
                "runtime_support_region_conversion": "Use optical continuation tube plus SAR support-region persistence; keep out of clean morphology.",
                "dynamic_model_need": "special_pool_dynamic_existence_model_needed",
                "limits": "manual review required; propagation boxes diagnostic only",
                "provenance_labels": "runtime_safe_temporal_evidence;SAR_temporal_observation;SAR_image_observation;manual_or_review_anchor;hypothesis_to_validate",
            }
        )
    sar_only = next((row for row in sar_temporal_rows if row.get("sample_pool") == "sar_only_gt_reference"), {})
    if sar_only:
        rows.append(
            {
                "probe_id": "D_sar_only",
                "sample_pool": "sar_only_gt_reference",
                "scene": sar_only.get("scene", ""),
                "object_hypothesis_id": "",
                "n_samples": sar_only.get("n_samples", ""),
                "optical_frame_span": "",
                "sar_frame_span": sar_only.get("sar_frame_span", ""),
                "optical_trajectory_signal": "none",
                "sar_gt_center_drift_signal": "SAR morphology reference only",
                "sar_peak_or_centroid_drift_signal": sar_only.get("gt_center_vs_peak_drift_label", ""),
                "dropout_or_temporal_support": "no optical object counterpart",
                "runtime_support_region_conversion": "Use only to design SAR observation descriptors.",
                "dynamic_model_need": "not_optical_sar_dynamic_correspondence",
                "limits": "excluded from optical-SAR correspondence",
                "provenance_labels": "SAR_image_observation;SAR_GT_posthoc_evidence",
            }
        )
    return rows


def anchor_tier(row: Mapping[str, str]) -> str:
    n = safe_float(row.get("n_paired_frames")) or 0
    peak = safe_float(row.get("paired_sar_peak_to_background_median")) or 0
    az = safe_float(row.get("azimuth_pass_rate"))
    drift = row.get("sar_local_peak_drift_label", "")
    if n >= 20 and peak >= 3 and drift == "local_peak_drift_consistent_with_sar_gt_center_posthoc":
        return "strong_but_review_gated_scene_or_object_anchor"
    if n >= 3 and peak >= 3 and drift.startswith("local_peak_drift"):
        if az is not None and az < 0.75:
            return "limited_anchor_low_azimuth_review_needed"
        return "candidate_anchor"
    return "insufficient_anchor"


def build_anchor_rows(
    object_rows: Sequence[Mapping[str, str]],
    scene_residuals: Sequence[Mapping[str, Any]],
    manual_review_rows: Sequence[Mapping[str, str]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for scene_row in scene_residuals:
        scene = str(scene_row.get("scene", ""))
        n = int(scene_row.get("n", 0))
        tier = "scene_anchor_dominant_but_not_global" if scene == "GM_RM017" else "scene_anchor_review_needed"
        rows.append(
            {
                "anchor_id": f"scene_{scene}",
                "scene": scene,
                "object_hypothesis_id": "",
                "sample_pool": "paired_optical_object_sar_gt",
                "n_samples": str(n),
                "optical_frame_span": "scene-level",
                "sar_frame_span": "scene-level",
                "anchor_type": "scene_level_azimuth_residual",
                "residual_or_latent_to_estimate": f"Delta_theta_s median={fmt(scene_row.get('median_azimuth_residual_deg'), 4)} deg; shell_ratio_median={fmt(scene_row.get('median_size_shell_ratio'), 4)}",
                "confidence_tier": tier,
                "evidence_summary": "High-confidence samples can estimate residuals only, not copy labels.",
                "use_allowed": "posthoc residual diagnosis and uncertainty calibration hypothesis",
                "use_forbidden": "writing Delta_theta_s into runtime prior without independent validation",
                "review_requirement": "GM_RM019 review before scene generalization" if scene == "GM_RM019" else "state-mix review before propagation",
                "next_action": "Estimate residuals after support-region SAR observation extraction.",
                "provenance_labels": "SAR_GT_posthoc_evidence;manual_or_review_anchor;hypothesis_to_validate",
            }
        )
    for index, row in enumerate(object_rows, start=1):
        tier = anchor_tier(row)
        if tier == "insufficient_anchor":
            allowed = "record as non-anchor or review candidate"
            next_action = "Collect more frames or review object continuity."
        else:
            allowed = "estimate object-level residual/uncertainty after review"
            next_action = "Use as review-gated anchor candidate; no label copying."
        rows.append(
            {
                "anchor_id": f"object_{index:02d}",
                "scene": row.get("scene", ""),
                "object_hypothesis_id": row.get("object_hypothesis_id", ""),
                "sample_pool": "paired_optical_object_sar_gt",
                "n_samples": row.get("n_paired_frames", ""),
                "optical_frame_span": row.get("optical_frame_span", ""),
                "sar_frame_span": row.get("sar_frame_span", ""),
                "anchor_type": "object_level_motion_or_sar_scatter_anchor",
                "residual_or_latent_to_estimate": "object azimuth residual, radial trend residual, SAR scatter morphology template",
                "confidence_tier": tier,
                "evidence_summary": f"az={row.get('azimuth_pass_rate')}; peak/bg={row.get('paired_sar_peak_to_background_median')}; drift={row.get('sar_local_peak_drift_label')}; reliability={row.get('trajectory_reliability_label')}",
                "use_allowed": allowed,
                "use_forbidden": "copying SAR labels or claiming identity truth",
                "review_requirement": row.get("review_need", ""),
                "next_action": next_action,
                "provenance_labels": "runtime_safe_optical_evidence;SAR_image_observation;SAR_GT_posthoc_evidence;manual_or_review_anchor;hypothesis_to_validate",
            }
        )
    high_review = [row for row in manual_review_rows if row.get("priority") == "high"]
    rows.append(
        {
            "anchor_id": "manual_review_high_priority",
            "scene": compact_counts(row.get("scene", "") for row in high_review),
            "object_hypothesis_id": "",
            "sample_pool": "manual_review_candidate_list",
            "n_samples": str(len(high_review)),
            "optical_frame_span": "see manual review CSV",
            "sar_frame_span": "see manual review CSV",
            "anchor_type": "review_gate_for_anchor_validity",
            "residual_or_latent_to_estimate": "which objects can serve as residual anchors after optical-side continuity review",
            "confidence_tier": "review_required_before_anchor_propagation",
            "evidence_summary": f"high priority review candidates={len(high_review)}",
            "use_allowed": "prioritize review work",
            "use_forbidden": "treating review-needed rows as already verified anchors",
            "review_requirement": "GM_RM019 manual optical review and GM_RM011 object stream recovery input check",
            "next_action": "Review first, then estimate residuals.",
            "provenance_labels": "manual_or_review_anchor;hypothesis_to_validate",
        }
    )
    return rows


def answer_questions() -> dict[str, str]:
    return {
        "1_why_weighted_sum_insufficient": "A flat weighted sum mixes different semantics: time/azimuth/shell/state are feasible-domain constraints, SAR image/temporal evidence are observation likelihoods, and SAR GT/review are posthoc validation. A single score can hide GT leakage, over-count GM_RM017 repeated frames, and treat dropout like clean morphology.",
        "2_feasible_domain_factors": "C_time, C_az, C_shell, and C_state should define the feasible SAR support. F_range_shape can only be a soft range-uncertainty modulator in reviewed complete states, not a hard domain constraint yet.",
        "3_sar_observation_likelihood": "F_sar_image and F_sar_temporal should form the SAR observation likelihood: peak/background, box/background, scatter concentration, centroid residual, long/short-axis morphology, and mainlobe/sidelobe-like diagnostics extracted inside optical-derived support regions.",
        "4_need_state_conditioning": "F_az, F_shell, F_range_shape, F_traj, F_sar_image, and F_sar_temporal all need state conditioning. Complete, edge/truncated, far-small, dropout, duplicate/handoff, SAR-only, GM_RM019, and GM_RM011 cannot share one global rule.",
        "5_need_dynamic_model": "Object-level dynamic modeling is needed for tracklets with multiple frames, especially state-mixed GM_RM017 objects, sparse/low-azimuth GM_RM019 objects, and dropout/no-match existence recovery. Single-frame optical box to single-frame SAR GT is the wrong unit.",
        "6_need_graph_matching": "Graph matching is needed when multiple optical object hypotheses, partial boxes, duplicate/handoff, or SAR scattering tubes compete for explanation, especially GM_RM019 and dropout cases. It is a future global explanation form, not a selector implemented here.",
        "7_anchor_candidates": "GM_RM017 scene/object rows provide many posthoc residual candidates but are state-mixed and GM_RM017-dominant. GM_RM019 object 0005/0080 are useful review-gated candidates but have low azimuth coverage/sparse frames. Anchors can estimate latent residuals, not copy labels.",
        "8_posthoc_observation_only": "SAR GT coverage, GT-crop peak/centroid drift, GT-crop box/background, manual/review anchors, SAR-only morphology, dropout SAR support, and MATLAB imaging concepts remain posthoc observation or reference-only.",
        "9_supported_vs_next": "Currently supported as model contracts: two-stage feasible-domain plus SAR observation, state conditioning, and dynamic temporal-tube framing. Next-step only: hierarchical scene/object residuals, product-of-experts calibration, graph matching, and anchor residual propagation.",
        "10_next_priority": "For the model itself, the first next step should be runtime support-region SAR peak/centroid extraction because it converts GT-crop SAR evidence into a usable SAR observation layer. GM_RM019 manual optical review is the next data-quality step for ambiguity; GM_RM011 object stream recovery is the next scale-expansion step.",
    }


def render_next_steps_doc(path: Path, timestamp: str, outputs: Mapping[str, str], answers: Mapping[str, str]) -> None:
    lines = [
        "# OTY2 Physical Factor Model Forms And Next Steps",
        "",
        f"Updated: {timestamp}",
        "",
        "This document records the OTY2 physical feasible-domain + SAR observation confirmation model sketch. It is not OTY3, not an automatic annotation proposal, not selector/ranking, and not training or threshold tuning.",
        "",
        "## Model Shift",
        "",
        "Do not collapse all factors into a flat weighted score:",
        "",
        "```text",
        "E = w_time F_time + w_az F_az + w_shell F_shell + w_sar_image F_sar_image + ...",
        "```",
        "",
        "Use a two-stage form instead:",
        "",
        "```text",
        "C_o,t = C_time(o,t) intersect C_az(o,t) intersect C_shell(o,t) intersect C_state(o,t)",
        "",
        "X*_o,1:T = argmax_{X_1:T in C_o,1:T} P(I_sar_1:T | X_1:T) P(X_1:T | O_1:T)",
        "```",
        "",
        "Equivalent energy form:",
        "",
        "```text",
        "X*_o,1:T = argmin_{X_1:T in C_o,1:T} E_sar_image(X_1:T) + E_sar_temporal(X_1:T) + E_optical_temporal(X_1:T, O_1:T)",
        "```",
        "",
        "The optical stream, timing, azimuth, vehicle shell, and state control the feasible domain. SAR image and SAR temporal evidence confirm the scattering structure inside that domain. SAR GT/manual/review fields validate and diagnose only.",
        "",
        "## State-Conditioned Forms",
        "",
        "```text",
        "P(X | O,I) = sum_s P(s | O) P(X | O,I,s)",
        "",
        "E(X,s) = E_state(s) + E(X | s)",
        "```",
        "",
        "- complete_visible: E_az + E_shell + E_range_shape + E_sar_image",
        "- edge/truncated: E_az + E_shell_relaxed + E_sar_temporal; range_shape only modulates uncertainty",
        "- far-small: E_time + E_az + E_sar_image",
        "- dropout: E_time + E_optical_temporal + E_sar_temporal; excluded from clean paired morphology",
        "- duplicate/handoff: review-needed object-hypothesis ambiguity; no identity truth",
        "",
        "## Factor Roles",
        "",
        "- Hard/semi-hard feasible-domain constraints: C_time, C_az, C_shell, C_state.",
        "- Soft optical hypothesis: F_range_shape, only after state conditioning.",
        "- SAR observation likelihood: F_sar_image and F_sar_temporal.",
        "- Posthoc validation only: SAR GT, GT-crop SAR image statistics, manual/review anchors.",
        "- Reference only: MATLAB/FMCW/SAR imaging toolbox concepts.",
        "",
        "## Priority Answer",
        "",
        answers["10_next_priority"],
        "",
        "## Generated Outputs",
        "",
    ]
    for name, output_path in outputs.items():
        lines.append(f"- {name}: `{output_path}`")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def render_report(
    path: Path,
    timestamp: str,
    summary: Mapping[str, Any],
    outputs: Mapping[str, str],
    sources: Mapping[str, str],
    answers: Mapping[str, str],
) -> None:
    lines = [
        "# OTY2 Physical Model Form Audit Report",
        "",
        f"生成时间：`{timestamp}`",
        "",
        "本报告推进到 `physical feasible-domain + SAR observation confirmation` 模型形式。它不是正式 OTY3，不输出最终自动标注，不做 selector/ranking，不训练或调阈值，不声明 identity truth。",
        "",
        "## Ledger And Boundary",
        "",
        f"- 442 ledger：`{json.dumps(summary['sample_ledger']['category_counts'], ensure_ascii=False)}`。",
        f"- paired frames/object hypotheses：`{summary['paired_frames']}` / `{summary['paired_object_hypotheses']}`。",
        f"- GM_RM017/GM_RM019 paired split：`{json.dumps(summary['scene_counts_paired'], ensure_ascii=False)}`。",
        "- GM_RM011 195 条是缺当前 OTY optical object stream，不是未标注。",
        "- SAR-only 20 条只作 SAR morphology/observation reference。",
        "- dropout/no-match 12 条只作 temporal continuation + SAR support 特殊机制池。",
        "",
        "## Recommended Model Form",
        "",
        "第一阶段定义可行域：",
        "",
        "```text",
        "C_o,t = C_time(o,t) intersect C_az(o,t) intersect C_shell(o,t) intersect C_state(o,t)",
        "```",
        "",
        "第二阶段在可行域内做 SAR observation confirmation：",
        "",
        "```text",
        "X*_o,1:T = argmax_{X_1:T in C_o,1:T} P(I_sar_1:T | X_1:T) P(X_1:T | O_1:T)",
        "```",
        "",
        "或能量形式：",
        "",
        "```text",
        "argmin E_sar_image(X_1:T) + E_sar_temporal(X_1:T) + E_optical_temporal(X_1:T,O_1:T)",
        "```",
        "",
        "## Ten Required Answers",
        "",
    ]
    for index, key in enumerate(answers, start=1):
        lines.append(f"{index}. {answers[key]}")
    lines.extend(
        [
            "",
            "## Current Support",
            "",
            f"- Current evidence supports the two-stage model as a design contract: temporal pass `{summary['key_metrics']['temporal_window_pass_rate']}`, azimuth original coverage `{summary['key_metrics']['azimuth_original_coverage']}`, tight shell `{summary['key_metrics']['tight_shell_coverage']}`, paired peak/background `{summary['key_metrics']['paired_peak_to_background_median']}`.",
            f"- State conditioning is required: `{summary['status_counts']}` plus dropout pool `12`.",
            f"- Dynamic model is partially supported: `{json.dumps(summary['trajectory_reliability_counts'], ensure_ascii=False)}`.",
            f"- Anchor propagation is review-gated: `{json.dumps(summary['anchor_confidence_counts'], ensure_ascii=False)}`.",
            "",
            "## Next-Step Ranking",
            "",
            "1. Runtime support-region SAR peak/centroid extraction: highest priority for the model form because it replaces GT-crop SAR observation with optical-derived support-region observation.",
            "2. GM_RM019 manual optical GT / identity-continuity review: needed before scene/object residual claims and graph matching examples are trusted.",
            "3. GM_RM011 object stream recovery: needed to expand object-level correspondence beyond the current 215 paired frames, using optical data only.",
            "",
            "## Outputs",
            "",
        ]
    )
    for name, output_path in outputs.items():
        lines.append(f"- {name}: `{output_path}`")
    lines.extend(["", "## Sources", ""])
    for name, source_path in sources.items():
        lines.append(f"- {name}: `{source_path}`")
    lines.extend(["", "## Boundary Flags", ""])
    for key, value in BOUNDARY_FLAGS.items():
        lines.append(f"- {key}: `{str(value).lower()}`")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_workspace_log(timestamp: str, outputs: Mapping[str, str], summary: Mapping[str, Any]) -> Path:
    WORKSPACE_LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = WORKSPACE_LOG_DIR / f"oty2_physical_model_form_audit_{timestamp}.log"
    lines = [
        f"timestamp={timestamp}",
        "task=oty2_physical_model_form_audit",
        r"interpreter=D:\MINICONDA\envs\py311\python.exe",
        f"outputs={json.dumps(outputs, ensure_ascii=False)}",
        f"summary={json.dumps(summary, ensure_ascii=False)}",
    ]
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return log_path


def run(args: argparse.Namespace) -> dict[str, Any]:
    timestamp = args.timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    inputs = load_inputs(args)
    physical_summary = inputs["physical_summary"]
    stratified_summary = inputs["stratified_summary"]
    ledger = validate_ledger(physical_summary)

    object_rows = inputs["object_rows"]
    sar_temporal_rows = inputs["sar_temporal_rows"]
    scene_residuals = scene_residual_rows(inputs["az_shell_rows"])
    answers = answer_questions()

    model_rows = build_model_form_rows(physical_summary, stratified_summary, object_rows, sar_temporal_rows)
    feasible_rows = build_feasible_domain_rows(physical_summary, stratified_summary)
    state_rows = build_state_rows(stratified_summary, object_rows)
    dynamic_rows = build_dynamic_rows(object_rows, sar_temporal_rows)
    anchor_rows = build_anchor_rows(object_rows, scene_residuals, inputs["manual_review_rows"])

    model_csv = REPORT_DIR / f"oty2_physical_model_form_comparison_{timestamp}.csv"
    feasible_csv = REPORT_DIR / f"oty2_feasible_domain_factor_audit_{timestamp}.csv"
    state_csv = REPORT_DIR / f"oty2_state_conditioned_model_probe_{timestamp}.csv"
    dynamic_csv = REPORT_DIR / f"oty2_dynamic_sar_observation_model_probe_{timestamp}.csv"
    anchor_csv = REPORT_DIR / f"oty2_anchor_propagation_candidate_audit_{timestamp}.csv"
    report_md = REPORT_DIR / f"oty2_physical_model_form_report_{timestamp}.md"
    summary_json = REPORT_DIR / f"oty2_physical_model_form_summary_{timestamp}.json"
    next_steps_doc = DOCS_DIR / "oty2_physical_factor_model_forms_and_next_steps.md"

    outputs = {
        "next_steps_doc": str(next_steps_doc),
        "physical_model_form_comparison_csv": str(model_csv),
        "feasible_domain_factor_audit_csv": str(feasible_csv),
        "state_conditioned_model_probe_csv": str(state_csv),
        "dynamic_sar_observation_model_probe_csv": str(dynamic_csv),
        "anchor_propagation_candidate_audit_csv": str(anchor_csv),
        "physical_model_form_report_md": str(report_md),
        "physical_model_form_summary_json": str(summary_json),
    }
    sources = {name: str(path) for name, path in inputs["paths"].items()}

    write_csv(model_csv, model_rows, MODEL_FORM_FIELDS)
    write_csv(feasible_csv, feasible_rows, FEASIBLE_DOMAIN_FIELDS)
    write_csv(state_csv, state_rows, STATE_FIELDS)
    write_csv(dynamic_csv, dynamic_rows, DYNAMIC_FIELDS)
    write_csv(anchor_csv, anchor_rows, ANCHOR_FIELDS)

    anchor_confidence_counts = dict(Counter(row["confidence_tier"] for row in anchor_rows))
    summary = {
        "timestamp": timestamp,
        "sample_ledger": ledger,
        "paired_frames": physical_summary.get("sample_ledger", {}).get("paired_count_rebuilt"),
        "paired_object_hypotheses": stratified_summary.get("object_level", {}).get("n_objects"),
        "scene_counts_paired": stratified_summary.get("scene_counts_paired", {}),
        "status_counts": stratified_summary.get("frame_level", {}).get("status_counts", ""),
        "trajectory_reliability_counts": stratified_summary.get("temporal_summary", {}).get("trajectory_reliability_counts", {}),
        "row_counts": {
            "model_form_comparison": len(model_rows),
            "feasible_domain_factor_audit": len(feasible_rows),
            "state_conditioned_model_probe": len(state_rows),
            "dynamic_sar_observation_model_probe": len(dynamic_rows),
            "anchor_propagation_candidate_audit": len(anchor_rows),
        },
        "key_metrics": {
            "temporal_window_pass_rate": stratified_summary.get("frame_level", {}).get("temporal_window_pass_rate"),
            "azimuth_original_coverage": physical_summary.get("key_metrics", {}).get("azimuth_original_coverage"),
            "tight_shell_coverage": physical_summary.get("key_metrics", {}).get("tight_shell_coverage"),
            "base_shell_coverage": physical_summary.get("key_metrics", {}).get("base_shell_coverage"),
            "paired_peak_to_background_median": physical_summary.get("key_metrics", {}).get("paired_peak_to_background_median"),
            "paired_box_to_background_median": physical_summary.get("key_metrics", {}).get("paired_box_to_background_median"),
        },
        "anchor_confidence_counts": anchor_confidence_counts,
        "recommended_next_step_ranked": [
            "runtime_support_region_sar_peak_centroid_extraction",
            "gmrm019_manual_optical_gt_identity_continuity_review",
            "gmrm011_object_stream_recovery",
        ],
        "question_answers": answers,
        "boundary_flags": BOUNDARY_FLAGS,
        "outputs": outputs,
        "sources": sources,
    }

    render_next_steps_doc(next_steps_doc, timestamp, outputs, answers)
    render_report(report_md, timestamp, summary, outputs, sources, answers)
    log_path = write_workspace_log(timestamp, outputs, summary)
    summary["outputs"]["workspace_log"] = str(log_path)
    write_json(summary_json, summary)
    print(json.dumps({"outputs": summary["outputs"], "row_counts": summary["row_counts"], "boundary_flags": BOUNDARY_FLAGS}, ensure_ascii=False, indent=2))
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timestamp", default="")
    parser.add_argument("--physical-factor-summary-json", default="")
    parser.add_argument("--factor-taxonomy-csv", default="")
    parser.add_argument("--joint-factor-probe-csv", default="")
    parser.add_argument("--object-ledger-csv", default="")
    parser.add_argument("--sar-temporal-csv", default="")
    parser.add_argument("--manual-review-csv", default="")
    parser.add_argument("--stratified-summary-json", default="")
    parser.add_argument("--az-shell-csv", default="")
    return parser


def main() -> None:
    run(build_parser().parse_args())


if __name__ == "__main__":
    main()
