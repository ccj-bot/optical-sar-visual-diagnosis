"""Generate GM_RM019 static physical factor hypothesis registry.

This is a static posthoc registry only. It reads frozen GM_RM019 artifacts and
does not create candidate boxes, ranking, selector outputs, final annotations,
revised GT, or identity claims.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import math
import shutil
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = REPO_ROOT / "reports" / "oty2"
SAMPLES_DIR = REPORT_DIR / "samples"
DATE = "20260712"
VERIFY_TMP_DIR = REPO_ROOT / "outputs" / "oty2_gm_rm019_static_physical_factor_registry_20260712" / "_verify_tmp"

INPUTS = {
    "local_response_units": SAMPLES_DIR / "oty2_wgv3_6a_a1_8a_r2_1_r1_1_local_response_units_20260711.csv",
    "boundary_variant_families": SAMPLES_DIR / "oty2_wgv3_6a_a1_8a_r2_1_r1_1_boundary_variant_families_20260711.csv",
    "same_object_candidate_edges": SAMPLES_DIR / "oty2_wgv3_6a_a1_8a_r2_1_r1_1_same_object_candidate_edges_20260711.csv",
    "proximity_residual_component_audit": SAMPLES_DIR / "oty2_wgv3_6a_a1_8a_r2_1_r1_1_proximity_residual_component_audit_20260711.csv",
    "response_unit_gt_instance_matrix": SAMPLES_DIR / "oty2_wgv3_6a_a1_8a_r2_1_r1_1_response_unit_gt_instance_matrix_20260711.csv",
    "boundary_family_gt_instance_matrix": SAMPLES_DIR / "oty2_wgv3_6a_a1_8a_r2_1_r1_1_boundary_family_gt_instance_matrix_20260711.csv",
    "focus_visual_review": SAMPLES_DIR / "oty2_wgv3_6a_a1_8a_r2_1_r1_1_focus_visual_review_20260711.csv",
    "background_counterexamples": SAMPLES_DIR / "oty2_wgv3_6a_a1_8a_r2_1_background_counterexamples_20260711.csv",
    "positive_negative_closure": SAMPLES_DIR / "oty2_wgv3_6a_a1_8a_positive_negative_closure_20260711.csv",
    "vehicle_structure_hypothesis": SAMPLES_DIR / "oty2_wgv3_6a_a1_8a_vehicle_structure_hypothesis_20260711.csv",
    "point_to_structure_ledger": SAMPLES_DIR / "oty2_wgv3_6a_a1_8a_point_to_structure_hypothesis_ledger_20260711.csv",
    "mask_observation_audit": SAMPLES_DIR / "oty2_wgv3_5a_r2c_gm019_mask_observation_audit_20260711.csv",
    "mask_failure_cases": SAMPLES_DIR / "oty2_wgv3_5a_r2c_gm019_failure_cases_20260711.csv",
    "optical_state_review": SAMPLES_DIR / "oty2_wgv3_5a_r2c_gm019_optical_state_review_20260711.csv",
    "paired_annotations": SAMPLES_DIR / "oty2_wgv3_5a_paired_annotations_20260710.csv",
}

OUTPUTS = {
    "report": REPORT_DIR / "oty2_gm_rm019_static_physical_factor_registry_20260712.md",
    "registry": SAMPLES_DIR / "oty2_gm_rm019_static_physical_factor_registry_20260712.csv",
    "counterexamples": SAMPLES_DIR / "oty2_gm_rm019_static_physical_factor_counterexamples_20260712.csv",
    "observations": SAMPLES_DIR / "oty2_gm_rm019_static_physical_factor_observations_20260712.csv",
}

REGISTRY_FIELDS = [
    "factor_id",
    "factor_name_cn",
    "status",
    "physical_hypothesis_cn",
    "measurable_observables",
    "fit_control_points",
    "gt_allowed_role",
    "gt_forbidden_interpretation",
    "current_support_evidence",
    "current_counterexamples",
    "applicability_conditions",
    "dynamic_confirmation_required",
    "gm017_validation_question",
    "source_artifacts",
    "representative_frames",
]

COUNTEREXAMPLE_FIELDS = [
    "counterexample_id",
    "factor_id",
    "counterexample_name_cn",
    "source_artifacts",
    "representative_frames",
    "counterexample_evidence_cn",
    "why_it_blocks_static_confirmation_cn",
    "applicability_boundary_cn",
    "gm017_validation_use_cn",
]

OBSERVATION_FIELDS = [
    "observation_id",
    "factor_id",
    "source_artifact",
    "metric",
    "value",
    "representative_frames",
    "interpretation_cn",
    "boundary_cn",
]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT)).replace("\\", "/")


def parse_float(value: Any, default: float = math.nan) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_box(text: str) -> tuple[float, float, float, float] | None:
    parts = [parse_float(part) for part in str(text or "").replace("|", ",").split(",")]
    if len(parts) != 4 or any(math.isnan(part) for part in parts):
        return None
    return parts[0], parts[1], parts[2], parts[3]


def box_width(box_text: str) -> float:
    box = parse_box(box_text)
    return abs(box[2] - box[0]) if box else math.nan


def box_height(box_text: str) -> float:
    box = parse_box(box_text)
    return abs(box[3] - box[1]) if box else math.nan


def fmt(value: float) -> str:
    if math.isnan(value):
        return ""
    return f"{value:.6f}".rstrip("0").rstrip(".")


def pct(num: int, den: int) -> str:
    return "0" if den == 0 else fmt(num / den)


def median(values: Iterable[float]) -> float:
    clean = sorted(value for value in values if not math.isnan(value))
    if not clean:
        return math.nan
    mid = len(clean) // 2
    if len(clean) % 2:
        return clean[mid]
    return (clean[mid - 1] + clean[mid]) / 2.0


def frames(rows: Sequence[Mapping[str, str]], field: str = "sar_frame", limit: int = 12) -> str:
    values = sorted({int(parse_float(row.get(field), -1)) for row in rows if parse_float(row.get(field), -1) >= 0})
    shown = values[:limit]
    suffix = "" if len(values) <= limit else f";...(+{len(values) - limit})"
    return ";".join(str(value) for value in shown) + suffix


def require_inputs() -> None:
    missing = [rel(path) for path in INPUTS.values() if not path.exists()]
    if missing:
        raise FileNotFoundError("missing required input files: " + "; ".join(missing))


def load_inputs() -> dict[str, list[dict[str, str]]]:
    require_inputs()
    return {name: read_rows(path) for name, path in INPUTS.items()}


def compute_observations(data: Mapping[str, Sequence[Mapping[str, str]]]) -> list[dict[str, str]]:
    units = data["local_response_units"]
    families = data["boundary_variant_families"]
    edges = data["same_object_candidate_edges"]
    residual = data["proximity_residual_component_audit"]
    bg = data["background_counterexamples"]
    closure = data["positive_negative_closure"]
    structures = data["vehicle_structure_hypothesis"]
    mask = data["mask_observation_audit"]
    gt_units = data["response_unit_gt_instance_matrix"]
    gt_families = data["boundary_family_gt_instance_matrix"]
    paired = [row for row in data["paired_annotations"] if row.get("scene") == "GM_RM019"]
    optical = data["optical_state_review"]

    unit_widths = [box_width(row.get("conservative_bbox", "")) for row in units]
    unit_heights = [box_height(row.get("conservative_bbox", "")) for row in units]
    width_dominant = sum(1 for w, h in zip(unit_widths, unit_heights) if not math.isnan(w) and not math.isnan(h) and w > h)
    height_dominant = sum(1 for w, h in zip(unit_widths, unit_heights) if not math.isnan(w) and not math.isnan(h) and h >= w)
    long_axis_values = [parse_float(row.get("long_axis_extent")) for row in structures]
    radial_values = [parse_float(row.get("radial_span")) for row in structures]
    azimuth_values = [parse_float(row.get("azimuth_span")) for row in structures]
    edge_counts = Counter(row.get("edge_type", "") for row in edges)
    spatial_counts = Counter(row.get("spatial_relation", "") for row in edges)
    residual_status = Counter(row.get("component_match_status", "") for row in residual)
    residual_proximity_true = sum(row.get("proximity_residual_candidate") == "true" for row in residual)
    center_supervision_false = sum(row.get("usable_for_center_supervision") == "false" for row in mask)
    interval_supervision_true = sum(row.get("usable_for_interval_supervision") == "true" for row in mask)
    mask_class_counts = Counter(row.get("sar_mask_observation_class", "") for row in mask)
    positive_insufficient = sum(row.get("physical_field_insufficient") == "true" for row in closure)
    gt_iou_values = [parse_float(row.get("iou")) for row in gt_units + gt_families]
    boundary_optical = [row for row in paired if "boundary_truncation_present" in row.get("visibility_state", "")]
    optical_allowed = sum(row.get("allowed_for_sar_mapping_audit") == "true" for row in optical)

    return [
        {
            "observation_id": "OBS_GM019_STATIC_001",
            "factor_id": "GM019_STATIC_H01",
            "source_artifact": rel(INPUTS["local_response_units"]) + ";" + rel(INPUTS["vehicle_structure_hypothesis"]),
            "metric": "local_unit_axis_distribution",
            "value": f"units={len(units)};width_dominant={width_dominant};height_dominant={height_dominant};median_unit_width_px={fmt(median(unit_widths))};median_unit_height_px={fmt(median(unit_heights))};median_structure_long_axis_px={fmt(median(long_axis_values))};median_radial_span_px={fmt(median(radial_values))};median_azimuth_span_px={fmt(median(azimuth_values))}",
            "representative_frames": frames(structures),
            "interpretation_cn": "方向性展宽可由既有局部响应框和结构观测量描述，适合作为替代 GT 框宽高的静态观测量。",
            "boundary_cn": "只描述 SAR 图像域响应形态，不解释为完整车辆尺寸或最终框。",
        },
        {
            "observation_id": "OBS_GM019_STATIC_002",
            "factor_id": "GM019_STATIC_H02",
            "source_artifact": rel(INPUTS["same_object_candidate_edges"]) + ";" + rel(INPUTS["point_to_structure_ledger"]),
            "metric": "candidate_edge_topology_counts",
            "value": f"same_object_candidate_edges={len(edges)};edge_type_counts={dict(sorted(edge_counts.items()))};spatial_relation_counts={dict(sorted(spatial_counts.items()))}",
            "representative_frames": frames(edges),
            "interpretation_cn": "主体、端点、侧向响应之间已有候选拓扑关系，但它们只表达同目标候选关系。",
            "boundary_cn": "候选边不是身份真值，也不是车辆部件确认。",
        },
        {
            "observation_id": "OBS_GM019_STATIC_003",
            "factor_id": "GM019_STATIC_H03",
            "source_artifact": rel(INPUTS["background_counterexamples"]) + ";" + rel(INPUTS["positive_negative_closure"]),
            "metric": "background_counterexample_pressure",
            "value": f"background_counterexamples={len(bg)};positive_negative_rows={len(closure)};physical_field_insufficient_rows={positive_insufficient}",
            "representative_frames": frames(bg, "same_frame"),
            "interpretation_cn": "固定背景、孤立小峰和背景弧线已经作为负向对照出现，适合登记为静态背景可解释性假设。",
            "boundary_cn": "背景可解释性不能直接成为硬规则；静态高响应可能闪烁。",
        },
        {
            "observation_id": "OBS_GM019_STATIC_004",
            "factor_id": "GM019_STATIC_H04",
            "source_artifact": rel(INPUTS["mask_observation_audit"]) + ";" + rel(INPUTS["mask_failure_cases"]) + ";" + rel(INPUTS["paired_annotations"]),
            "metric": "near_field_mask_boundary_semantics",
            "value": f"mask_rows={len(mask)};center_supervision_false={center_supervision_false};interval_supervision_true={interval_supervision_true};mask_class_counts={dict(sorted(mask_class_counts.items()))};paired_rows={len(paired)};paired_boundary_truncation_rows={len(boundary_optical)};optical_state_allowed_for_sar_mapping_audit={optical_allowed}",
            "representative_frames": frames(mask),
            "interpretation_cn": "近场扇形/遮罩边界会改变可见响应中心的含义，更适合做区间或重叠控制点。",
            "boundary_cn": "不能用 GT 或遮罩内响应中心直接确认完整车辆中心。",
        },
        {
            "observation_id": "OBS_GM019_STATIC_005",
            "factor_id": "GM019_STATIC_H05",
            "source_artifact": rel(INPUTS["proximity_residual_component_audit"]) + ";" + rel(INPUTS["response_unit_gt_instance_matrix"]) + ";" + rel(INPUTS["boundary_family_gt_instance_matrix"]),
            "metric": "residual_proximity_and_gt_control",
            "value": f"component_rows={len(residual)};residual_status_counts={dict(sorted(residual_status.items()))};proximity_residual_candidates={residual_proximity_true};gt_matrix_rows={len(gt_units) + len(gt_families)};max_eval_iou={fmt(max(gt_iou_values or [math.nan]))}",
            "representative_frames": frames(residual),
            "interpretation_cn": "弱 residual 响应靠近冻结区域，但是否为车辆弱响应仍需多阈值持续性和动态共运动验证。",
            "boundary_cn": "GT 只能作为事后控制坐标；proximity residual 不能变成新 Gate 或 Top-K 选择依据。",
        },
    ]


def build_registry(observations: Sequence[Mapping[str, str]]) -> list[dict[str, str]]:
    obs_by_factor = {row["factor_id"]: row for row in observations}
    return [
        {
            "factor_id": "GM019_STATIC_H01",
            "factor_name_cn": "距离向-方位向方向性展宽的图像域替代观测量",
            "status": "hypothesis",
            "physical_hypothesis_cn": "同一局部响应对象在 SAR 图像域可能表现出距离向或方位向的非对称展宽；方向性展宽比 GT 框宽高更接近静态散射支撑观测，但仍不等于真实车辆尺寸。",
            "measurable_observables": "局部响应框宽高、长轴/短轴、radial_span、azimuth_span、边界族不确定包络、方向主导类别。",
            "fit_control_points": "GT 中心、GT 局部区域、R1.1 response-unit / boundary-family GT-instance 矩阵；只用于事后拟合误差和坐标参考。",
            "gt_allowed_role": "GT 可提供局部坐标锚点、距离/方位参考和形态拟合误差。",
            "gt_forbidden_interpretation": "GT 不能确认散射支撑尺寸、不能把局部响应扩展成完整车辆框，不能用于选择唯一响应单元。",
            "current_support_evidence": obs_by_factor["GM019_STATIC_H01"]["value"],
            "current_counterexamples": "GT 框宽高不等于真实散射支撑；背景弧线或近场边界也能形成长条形响应。",
            "applicability_conditions": "仅适用于已有冻结局部响应对象和边界族；需要同时保留背景反例和遮罩边界状态。",
            "dynamic_confirmation_required": "true",
            "gm017_validation_question": "在 GM_RM017 连续窗口中，方向性展宽是否比 GT 框宽高更稳定地解释响应支撑，并避免 F4 尺度拟合失败？",
            "source_artifacts": obs_by_factor["GM019_STATIC_H01"]["source_artifact"],
            "representative_frames": obs_by_factor["GM019_STATIC_H01"]["representative_frames"],
        },
        {
            "factor_id": "GM019_STATIC_H02",
            "factor_name_cn": "主体核心-端点热点-侧向响应的候选拓扑",
            "status": "hypothesis",
            "physical_hypothesis_cn": "主体核心、端点热点和侧向响应的相对位置可形成静态候选拓扑，用于提出同目标候选关系，但不能单帧确认同一车辆或真实部件。",
            "measurable_observables": "accepted graph link 计数、part-part 候选边、中心距离、bbox gap、spatial_relation、共享核心原子。",
            "fit_control_points": "GT 局部区域可检查候选拓扑是否落在目标附近；focus visual review 可作人工审阅线索。",
            "gt_allowed_role": "GT 可检查拓扑是否位于事后目标区域附近，并提供正负对照。",
            "gt_forbidden_interpretation": "GT 不能把候选边升级为同车真值，不能确认端点或侧向响应是车辆物理部件。",
            "current_support_evidence": obs_by_factor["GM019_STATIC_H02"]["value"],
            "current_counterexamples": "孤立端点样小峰、邻近车辆和非共享核心响应可产生类似拓扑。",
            "applicability_conditions": "必须有主体核心或已冻结局部响应对象；孤立热点不得单独进入该因素。",
            "dynamic_confirmation_required": "true",
            "gm017_validation_question": "在 GM_RM017 连续窗口中，候选拓扑是否随共同运动保持相对稳定，且能排除邻车短时同向造成的假拓扑？",
            "source_artifacts": obs_by_factor["GM019_STATIC_H02"]["source_artifact"],
            "representative_frames": obs_by_factor["GM019_STATIC_H02"]["representative_frames"],
        },
        {
            "factor_id": "GM019_STATIC_H03",
            "factor_name_cn": "固定背景结构和孤立小峰的静态可解释性",
            "status": "hypothesis",
            "physical_hypothesis_cn": "固定背景、背景弧线、道路边缘或孤立小峰可解释一部分高响应；静态背景可解释性应作为负向对照，而不是车辆支持。",
            "measurable_observables": "background_counterexamples 数量、alternative_exclusion_reason、isolated_small_atom / background_arc 角色、positive-negative closure 中的负向排除说明。",
            "fit_control_points": "GT 外邻近区域、已记录背景反例、非车辆 pair 和 focus 帧审阅说明。",
            "gt_allowed_role": "GT 可标定目标局部区域和邻近非目标对照带。",
            "gt_forbidden_interpretation": "GT 不能证明 GT 外亮点必为背景，也不能把稳定高响应直接变成硬拒绝规则。",
            "current_support_evidence": obs_by_factor["GM019_STATIC_H03"]["value"],
            "current_counterexamples": "固定背景可能闪烁；静止或慢速车辆也可能短时呈现稳定高响应。",
            "applicability_conditions": "只作为负向解释和反例登记；必须保留 unresolved 状态，不能覆盖动态证据。",
            "dynamic_confirmation_required": "true",
            "gm017_validation_question": "在 GM_RM017 中，F2 背景稳定性如何结合 F3 间歇可见，避免把背景闪烁误作车辆弱响应？",
            "source_artifacts": obs_by_factor["GM019_STATIC_H03"]["source_artifact"],
            "representative_frames": obs_by_factor["GM019_STATIC_H03"]["representative_frames"],
        },
        {
            "factor_id": "GM019_STATIC_H04",
            "factor_name_cn": "近场扇形边界接触与可见响应中心审慎解释",
            "status": "hypothesis",
            "physical_hypothesis_cn": "近场遮罩、扇形边界或图像边界接触会使 SAR 可见响应中心偏离完整车辆中心；应优先登记为区间/重叠控制问题，而不是中心监督。",
            "measurable_observables": "mask class、center supervision 可用性、interval supervision 可用性、bottom valid margin、mask boundary distance、optical visibility_state 中的 boundary_truncation。",
            "fit_control_points": "GT 中心、遮罩交叠比例、mask boundary distance 和可见响应框；只用于事后审查可见区域。",
            "gt_allowed_role": "GT 可测试遮罩内可见响应与标注区域的重叠关系。",
            "gt_forbidden_interpretation": "GT 不能确认遮罩内响应中心就是完整车辆中心，不能用于修正最终框。",
            "current_support_evidence": obs_by_factor["GM019_STATIC_H04"]["value"],
            "current_counterexamples": "并非所有边界接触都表示真实截断；无局部热带或背景边缘也可触发边界接触。",
            "applicability_conditions": "仅适用于 mask/扇形边界接触、近距边界或 optical 状态提示存在截断风险的帧。",
            "dynamic_confirmation_required": "true",
            "gm017_validation_question": "GM_RM017 留出窗口中，边界接触样本能否通过连续可见响应区间验证，而不是用中心误差强行拟合？",
            "source_artifacts": obs_by_factor["GM019_STATIC_H04"]["source_artifact"],
            "representative_frames": obs_by_factor["GM019_STATIC_H04"]["representative_frames"],
        },
        {
            "factor_id": "GM019_STATIC_H05",
            "factor_name_cn": "弱 residual 响应的多阈值持续性与 PSF 旁瓣区分",
            "status": "hypothesis",
            "physical_hypothesis_cn": "靠近冻结响应区域的弱 residual 可能包含被阈值遗漏的散射支撑，也可能只是 PSF 旁瓣、噪声或背景纹理；需要多阈值持续性和动态共运动来区分。",
            "measurable_observables": "residual_component_status、proximity_residual_candidate、component_energy、component_area、near_frozen_core、near_boundary_family、跨阈值持续性。",
            "fit_control_points": "GT 局部区域、冻结响应单元、边界族和 residual 近邻关系；用于事后测量，不用于新增候选。",
            "gt_allowed_role": "GT 可作为局部区域控制点，比较 weak residual 是否反复出现在目标附近。",
            "gt_forbidden_interpretation": "GT 不能把 residual 直接确认成车辆弱部件，不能据此增加 Gate、Top-K 规则或候选排序。",
            "current_support_evidence": obs_by_factor["GM019_STATIC_H05"]["value"],
            "current_counterexamples": "大量 dropped residual 不靠近冻结区域；PSF 旁瓣、道路边缘和背景纹理可能伪装成弱侧向响应。",
            "applicability_conditions": "只适用于已完成 residual_semantics_fix 后的 dropped residual 行；必须排除已匹配冻结原子行。",
            "dynamic_confirmation_required": "true",
            "gm017_validation_question": "在 GM_RM017 中，弱 residual 是否能在多阈值和连续窗口中保持与主体响应共运动，并与 PSF 旁瓣分离？",
            "source_artifacts": obs_by_factor["GM019_STATIC_H05"]["source_artifact"],
            "representative_frames": obs_by_factor["GM019_STATIC_H05"]["representative_frames"],
        },
    ]


def build_counterexamples() -> list[dict[str, str]]:
    return [
        {
            "counterexample_id": "GM019_STATIC_CE01",
            "factor_id": "GM019_STATIC_H01",
            "counterexample_name_cn": "GT 框宽高不等于散射支撑尺寸",
            "source_artifacts": rel(INPUTS["point_to_structure_ledger"]) + ";" + rel(INPUTS["background_counterexamples"]),
            "representative_frames": "27;29;30;31",
            "counterexample_evidence_cn": "既有 ledger 已指出几何尺度是像素坐标响应尺度；背景弧线和长条响应也可产生方向性展宽。",
            "why_it_blocks_static_confirmation_cn": "单帧方向性展宽无法确认真实车辆长宽或散射部件身份。",
            "applicability_boundary_cn": "只能作为拟合观测量，不作为车辆尺寸 Gate。",
            "gm017_validation_use_cn": "替代 F4 的 GT 框宽高拟合，转向响应支撑方向性和连续窗口稳定性。",
        },
        {
            "counterexample_id": "GM019_STATIC_CE02",
            "factor_id": "GM019_STATIC_H02",
            "counterexample_name_cn": "孤立端点样小峰和邻车可伪装拓扑",
            "source_artifacts": rel(INPUTS["background_counterexamples"]) + ";" + rel(INPUTS["same_object_candidate_edges"]),
            "representative_frames": "27;28;29;30;31",
            "counterexample_evidence_cn": "background counterexamples 记录 isolated_small_atom / unresolved_atom 缺少 whole-core membership 证据。",
            "why_it_blocks_static_confirmation_cn": "端点或侧向关系若缺少共享核心或动态共同运动，不能确认是同一目标部件。",
            "applicability_boundary_cn": "必须保留为候选边；孤立热点不得单独闭合。",
            "gm017_validation_use_cn": "用 F1 共运动和邻车反例测试候选拓扑是否保持相对关系。",
        },
        {
            "counterexample_id": "GM019_STATIC_CE03",
            "factor_id": "GM019_STATIC_H03",
            "counterexample_name_cn": "固定背景闪烁和稳定高响应",
            "source_artifacts": rel(INPUTS["positive_negative_closure"]) + ";GM_RM017 counterexample CE_F2_N005/CE_F3_BACKGROUND_FLICKER read-only",
            "representative_frames": "27;28;29;30;31",
            "counterexample_evidence_cn": "正负闭环表多行标记 physical_field_insufficient；GM_RM017 参考中固定背景可稳定也可闪烁。",
            "why_it_blocks_static_confirmation_cn": "静态稳定或间歇出现本身不能证明车辆，也不能证明背景硬拒绝。",
            "applicability_boundary_cn": "只能作负向解释，不能变成硬 Gate。",
            "gm017_validation_use_cn": "用 F2/F3 联合测试背景稳定与可见性间歇的边界。",
        },
        {
            "counterexample_id": "GM019_STATIC_CE04",
            "factor_id": "GM019_STATIC_H04",
            "counterexample_name_cn": "遮罩内响应中心不是完整车辆中心",
            "source_artifacts": rel(INPUTS["mask_observation_audit"]) + ";" + rel(INPUTS["mask_failure_cases"]),
            "representative_frames": "0;4;8;27;31",
            "counterexample_evidence_cn": "mask audit 多行 center supervision=false，但 interval/masked-overlap evaluation 可用；failure cases 记录 center semantics risk。",
            "why_it_blocks_static_confirmation_cn": "近场边界接触会改变中心语义，不能用中心误差确认车辆区域。",
            "applicability_boundary_cn": "仅用于边界/遮罩接触场景的审慎解释。",
            "gm017_validation_use_cn": "在连续窗口中验证可见响应区间，而不是中心点。",
        },
        {
            "counterexample_id": "GM019_STATIC_CE05",
            "factor_id": "GM019_STATIC_H05",
            "counterexample_name_cn": "PSF 旁瓣、纹理噪声和非邻近 residual",
            "source_artifacts": rel(INPUTS["proximity_residual_component_audit"]),
            "representative_frames": "27;28;29;30;31;78;79;80;81",
            "counterexample_evidence_cn": "修正后 residual 表仍有非 proximity dropped residual，并且 matched frozen atom 行已排除 residual 计数。",
            "why_it_blocks_static_confirmation_cn": "弱响应靠近目标区域也可能是旁瓣或背景纹理；单帧不能判定弱车辆部件。",
            "applicability_boundary_cn": "必须先通过多阈值持续性和动态共运动，再进入后续验证。",
            "gm017_validation_use_cn": "用连续窗口测试弱 residual 是否与主体响应共同漂移。",
        },
    ]


def render_report(registry: Sequence[Mapping[str, str]], counterexamples: Sequence[Mapping[str, str]], observations: Sequence[Mapping[str, str]], replay_status: str, replay_evidence: str) -> str:
    lines = [
        "# GM_RM019 静态物理因素假设登记表 v0",
        "",
        "OTY2（Optical Timeline Y2，光学时序辅助阶段二）本轮仅登记 SAR（Synthetic Aperture Radar，合成孔径雷达）静态图像域的物理因素假设。GT（Ground Truth，真值标注）只作为事后控制点。PSF（Point Spread Function，点扩散函数）只作为弱响应反例解释之一。",
        "",
        "## 边界",
        "",
        "- 状态全部为 `hypothesis`。",
        "- 不生成候选框，不修改 bbox，不做 selector、ranking、best box、最终标注、GT 修改、身份闭合或加权总分。",
        "- 散射原子不是车辆；局部响应单元不是完整车辆；边界变体族只表达同一局部响应核心的不同边界；同目标候选关系不是同车真值。",
        "- GM_RM017 只作为方法、留出验证设计和反例来源；本报告不把 GM_RM017 结论复制成 GM_RM019 结论。",
        "",
        "## Part A 依赖状态",
        "",
        "- residual 语义修正已完成：全量 component audit rows=2368，matched frozen-atom / non-residual rows=52，真正 dropped residual rows=2316，proximity residual candidates=1563，unknown match-status rows=0。",
        "- 因此 Part B 使用修正后的 residual 表，且不把 2368 行整体解释为 residual。",
        "",
        "## 登记因素",
        "",
    ]
    for row in registry:
        lines.extend(
            [
                f"### {row['factor_id']} {row['factor_name_cn']}",
                "",
                f"- status: `{row['status']}`",
                f"- 物理假设：{row['physical_hypothesis_cn']}",
                f"- 可测观测量：{row['measurable_observables']}",
                f"- 可用于拟合的确认点：{row['fit_control_points']}",
                f"- GT 可以拟合或提供：{row['gt_allowed_role']}",
                f"- GT 不能确认：{row['gt_forbidden_interpretation']}",
                f"- 当前支持证据：{row['current_support_evidence']}",
                f"- 当前反例：{row['current_counterexamples']}",
                f"- 适用条件：{row['applicability_conditions']}",
                f"- 必须动态确认：{row['dynamic_confirmation_required']}",
                f"- 需要在 GM_RM017 验证的问题：{row['gm017_validation_question']}",
                f"- 来源文件：{row['source_artifacts']}",
                f"- 代表帧：{row['representative_frames']}",
                "",
            ]
        )
    lines.extend(
        [
            "## 反例索引",
            "",
            "| counterexample_id | factor_id | 反例 | 代表帧 | 边界 |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for row in counterexamples:
        lines.append(
            f"| {row['counterexample_id']} | {row['factor_id']} | {row['counterexample_name_cn']} | {row['representative_frames']} | {row['applicability_boundary_cn']} |"
        )
    lines.extend(
        [
            "",
            "## GM_RM017 参考边界",
            "",
            "- F1 共运动在单一线程中获得支持，但邻车可能短时同向；GM_RM019 只能把拓扑/弱响应送去验证。",
            "- F2 固定背景稳定性获得支持，但固定背景可能闪烁，不得成为硬 Gate。",
            "- F3 局部响应间歇可见只有部分支持，背景闪烁是反例。",
            "- F4 尺度-距离/方位关系在留出集劣于常量尺寸；GM_RM019 应改用方向性展宽、响应支撑和边界状态，而不是 GT 框宽高。",
            "- F5 光学-SAR 趋势只有弱符号一致性，精确时间戳和偏移仍未解决。",
            "",
            "## 观测表摘要",
            "",
        ]
    )
    for row in observations:
        lines.append(f"- {row['observation_id']} / {row['factor_id']}: {row['metric']} = `{row['value']}`")
    lines.extend(
        [
            "",
            "## Replay",
            "",
            f"- verify-static-registry: `{replay_status}`",
            f"- replay evidence: `{replay_evidence}`",
            "",
            "## 输出文件",
            "",
            *[f"- `{rel(path)}`" for path in OUTPUTS.values()],
            "",
        ]
    )
    return "\n".join(lines)


def build_outputs() -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    data = load_inputs()
    observations = compute_observations(data)
    registry = build_registry(observations)
    counterexamples = build_counterexamples()
    return registry, counterexamples, observations


def write_outputs(replay_status: str = "PENDING", replay_evidence: str = "pending until verify-static-registry") -> None:
    registry, counterexamples, observations = build_outputs()
    write_csv(OUTPUTS["registry"], registry, REGISTRY_FIELDS)
    write_csv(OUTPUTS["counterexamples"], counterexamples, COUNTEREXAMPLE_FIELDS)
    write_csv(OUTPUTS["observations"], observations, OBSERVATION_FIELDS)
    write_text(OUTPUTS["report"], render_report(registry, counterexamples, observations, replay_status, replay_evidence))
    print(f"generate complete registry={len(registry)} counterexamples={len(counterexamples)} observations={len(observations)}")


def verify_static_registry() -> None:
    for path in OUTPUTS.values():
        if not path.exists():
            raise FileNotFoundError(f"missing output before verify: {rel(path)}")
    if VERIFY_TMP_DIR.exists():
        shutil.rmtree(VERIFY_TMP_DIR)
    VERIFY_TMP_DIR.mkdir(parents=True, exist_ok=True)
    registry, counterexamples, observations = build_outputs()
    temp_outputs = {
        "registry": VERIFY_TMP_DIR / OUTPUTS["registry"].name,
        "counterexamples": VERIFY_TMP_DIR / OUTPUTS["counterexamples"].name,
        "observations": VERIFY_TMP_DIR / OUTPUTS["observations"].name,
        "report": VERIFY_TMP_DIR / OUTPUTS["report"].name,
    }
    write_csv(temp_outputs["registry"], registry, REGISTRY_FIELDS)
    write_csv(temp_outputs["counterexamples"], counterexamples, COUNTEREXAMPLE_FIELDS)
    write_csv(temp_outputs["observations"], observations, OBSERVATION_FIELDS)
    temp_evidence = "registry:PENDING; counterexamples:PENDING; observations:PENDING"
    write_text(temp_outputs["report"], render_report(registry, counterexamples, observations, "PENDING", temp_evidence))
    csv_results = {
        key: sha256(temp_outputs[key]) == sha256(OUTPUTS[key])
        for key in ["registry", "counterexamples", "observations"]
    }
    replay_status = "PASS" if all(csv_results.values()) else "FAIL"
    replay_evidence = "; ".join(f"{key}:{'PASS' if value else 'FAIL'}" for key, value in csv_results.items())
    write_text(OUTPUTS["report"], render_report(registry, counterexamples, observations, replay_status, replay_evidence))
    write_text(temp_outputs["report"], render_report(registry, counterexamples, observations, replay_status, replay_evidence))
    report_ok = sha256(temp_outputs["report"]) == sha256(OUTPUTS["report"])
    replay_status = "PASS" if all(csv_results.values()) and report_ok else "FAIL"
    replay_evidence = replay_evidence + f"; report:{'PASS' if report_ok else 'FAIL'}"
    write_text(OUTPUTS["report"], render_report(registry, counterexamples, observations, replay_status, replay_evidence))
    print(f"verify-static-registry={replay_status}")
    print(replay_evidence)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["generate", "verify-static-registry"])
    args = parser.parse_args()
    if args.command == "generate":
        write_outputs()
    elif args.command == "verify-static-registry":
        verify_static_registry()


if __name__ == "__main__":
    main()
