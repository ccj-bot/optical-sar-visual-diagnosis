#!/usr/bin/env python
"""Build WGV1.4 auto visual thread audit and repair artifacts.

This script records a visual audit over the existing WGV1.3 review PNG pack.
It reads WGV1.3 manifests, applies visual thread/edge repair decisions, and
writes WGV1.4 diagnostic-only CSV/Markdown artifacts. It does not run a
detector, tracker replay, SAR pairing, selector/ranker, or annotation export.
"""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLES_DIR = REPO_ROOT / "reports/oty2/samples"
REPORTS_DIR = REPO_ROOT / "reports/oty2"

THREAD_MANIFEST = SAMPLES_DIR / "oty2_yolo26l_wgv1_3_vehicle_thread_review_pack_manifest_20260708.csv"
FRAME_MANIFEST = SAMPLES_DIR / "oty2_yolo26l_wgv1_3_vehicle_thread_review_pack_frame_manifest_20260708.csv"
EDGE_FRAME_MANIFEST = SAMPLES_DIR / "oty2_yolo26l_wgv1_3_vehicle_thread_review_pack_edge_frame_manifest_20260708.csv"
SPLIT_TABLE = SAMPLES_DIR / "oty2_yolo26l_wgv1_3_identity_safe_target_family_split_20260708.csv"
MERGE_TABLE = SAMPLES_DIR / "oty2_yolo26l_wgv1_3_single_vehicle_temporal_merge_candidates_20260708.csv"

REPORT = REPORTS_DIR / "oty2_yolo26l_wgv1_4_auto_visual_thread_audit_and_repair_20260708.md"
SPOTCHECK = REPORTS_DIR / "oty2_yolo26l_wgv1_4_user_spotcheck_only_20260708.md"
THREADS_OUT = SAMPLES_DIR / "oty2_yolo26l_wgv1_4_vehicle_threads_20260708.csv"
FRAGMENTS_OUT = SAMPLES_DIR / "oty2_yolo26l_wgv1_4_vehicle_fragments_20260708.csv"
SAME_EDGES_OUT = SAMPLES_DIR / "oty2_yolo26l_wgv1_4_same_vehicle_edges_20260708.csv"
CONTEXT_EDGES_OUT = SAMPLES_DIR / "oty2_yolo26l_wgv1_4_temporal_context_edges_20260708.csv"
BLOCKED_OUT = SAMPLES_DIR / "oty2_yolo26l_wgv1_4_blocked_review_items_20260708.csv"
CHANGELOG_OUT = SAMPLES_DIR / "oty2_yolo26l_wgv1_3_to_v1_4_visual_audit_change_log_20260708.csv"

NO_SAR = "no / blocked"


WGV14_THREADS = [
    {
        "wgv1_4_thread_id": "GM_RM011_WGV14T001",
        "scene_id": "GM_RM011",
        "target_family_ids": [
            "GM_RM011_WGV12TF001",
            "GM_RM011_WGV12TF002",
            "GM_RM011_WGV12TF003",
            "GM_RM011_WGV12TF004",
            "GM_RM011_WGV12TF005",
        ],
        "wgv1_4_status": "accepted",
        "visual_identity_label": "GM_RM011_white_car_nearfield_000_025",
        "same_vehicle_edge_ids": "GM_RM011_WGV12M001;GM_RM011_WGV12M002;GM_RM011_WGV12M003;GM_RM011_WGV12M004",
        "blocked_edge_ids": "",
        "context_edge_ids": "",
        "confidence": "high",
        "auto_applied": "yes",
        "needs_user_spotcheck": "no",
        "visual_summary": "White near-field car remains the same referent from side-window crop through front/hood crop; M003 primary-box issue is duplicate/better-box, not a vehicle switch.",
        "rule_triggered": "A;B;D;G",
        "evidence_frames": [8, 9, 10, 13, 18, 24, 25],
    },
    {
        "wgv1_4_thread_id": "GM_RM011_WGV14T002",
        "scene_id": "GM_RM011",
        "target_family_ids": ["GM_RM011_WGV12TF006"],
        "wgv1_4_status": "accepted",
        "visual_identity_label": "GM_RM011_white_front_car_031_035",
        "same_vehicle_edge_ids": "",
        "blocked_edge_ids": "GM_RM011_WGV12M005",
        "context_edge_ids": "GM_RM011_WGV14C001",
        "confidence": "high",
        "auto_applied": "yes",
        "needs_user_spotcheck": "no",
        "visual_summary": "Standalone white front-facing car; M005 shows same-color replacement from the preceding near-field white car, so it remains separated.",
        "rule_triggered": "D;F",
        "evidence_frames": [31, 32, 33, 34, 35],
    },
    {
        "wgv1_4_thread_id": "GM_RM011_WGV14T003",
        "scene_id": "GM_RM011",
        "target_family_ids": ["GM_RM011_WGV12TF007"],
        "wgv1_4_status": "accepted",
        "visual_identity_label": "GM_RM011_white_car_competition_135_137",
        "same_vehicle_edge_ids": "",
        "blocked_edge_ids": "",
        "context_edge_ids": "",
        "confidence": "high",
        "auto_applied": "yes",
        "needs_user_spotcheck": "no",
        "visual_summary": "Independent three-frame white/gray vehicle competition scene with no adjacent merge candidate.",
        "rule_triggered": "A;G",
        "evidence_frames": [135, 136, 137],
    },
    {
        "wgv1_4_thread_id": "GM_RM011_WGV14T004",
        "scene_id": "GM_RM011",
        "target_family_ids": ["GM_RM011_WGV12TF008", "GM_RM011_WGV12TF009"],
        "wgv1_4_status": "accepted",
        "visual_identity_label": "GM_RM011_white_car_scooter_context_151_166",
        "same_vehicle_edge_ids": "GM_RM011_WGV12M006",
        "blocked_edge_ids": "",
        "context_edge_ids": "",
        "confidence": "high",
        "auto_applied": "yes",
        "needs_user_spotcheck": "no",
        "visual_summary": "Same white car passes near a scooter and covered vehicle; the final frames are edge-visible but still continuous.",
        "rule_triggered": "B;G",
        "evidence_frames": [151, 154, 160, 164, 166],
    },
    {
        "wgv1_4_thread_id": "GM_RM011_WGV14T005",
        "scene_id": "GM_RM011",
        "target_family_ids": [
            "GM_RM011_WGV12TF010",
            "GM_RM011_WGV12TF011",
            "GM_RM011_WGV12TF012",
            "GM_RM011_WGV12TF013",
            "GM_RM011_WGV12TF014",
            "GM_RM011_WGV12TF015",
            "GM_RM011_WGV12TF016",
            "GM_RM011_WGV12TF017",
            "GM_RM011_WGV12TF018",
            "GM_RM011_WGV12TF019",
        ],
        "wgv1_4_status": "accepted",
        "visual_identity_label": "GM_RM011_white_car_underpass_nearfield_231_288",
        "same_vehicle_edge_ids": "GM_RM011_WGV12M007;GM_RM011_WGV12M008;GM_RM011_WGV12M009;GM_RM011_WGV12M010;GM_RM011_WGV12M011;GM_RM011_WGV12M012;GM_RM011_WGV12M013;GM_RM011_WGV12M014;GM_RM011_WGV12M015",
        "blocked_edge_ids": "GM_RM011_WGV12M016",
        "context_edge_ids": "GM_RM011_WGV14C002",
        "confidence": "medium_high",
        "auto_applied": "yes",
        "needs_user_spotcheck": "yes",
        "visual_summary": "Long underpass near-field white-car sequence; WGV1.3 over-split it. The 286-288 competitor white SUV makes this a high-risk accepted repair.",
        "rule_triggered": "B;F;G",
        "evidence_frames": [231, 233, 242, 250, 259, 270, 279, 288],
    },
    {
        "wgv1_4_thread_id": "GM_RM011_WGV14T006",
        "scene_id": "GM_RM011",
        "target_family_ids": ["GM_RM011_WGV12TF020"],
        "wgv1_4_status": "accepted",
        "visual_identity_label": "GM_RM011_competitor_white_suv_289_292",
        "same_vehicle_edge_ids": "",
        "blocked_edge_ids": "GM_RM011_WGV12M016",
        "context_edge_ids": "GM_RM011_WGV14C002",
        "confidence": "high",
        "auto_applied": "yes",
        "needs_user_spotcheck": "no",
        "visual_summary": "Separate white SUV at left/rear after frame 289; it is not the right-side white car tracked in WGV14T005.",
        "rule_triggered": "D;F;G",
        "evidence_frames": [287, 288, 289, 290, 292],
    },
    {
        "wgv1_4_thread_id": "GM_RM017_WGV14T001",
        "scene_id": "GM_RM017",
        "target_family_ids": [
            "GM_RM017_WGV12TF001",
            "GM_RM017_WGV12TF002",
            "GM_RM017_WGV12TF004",
        ],
        "wgv1_4_status": "weak",
        "visual_identity_label": "GM_RM017_white_box_truck_118_157",
        "same_vehicle_edge_ids": "GM_RM017_WGV12M001;GM_RM017_WGV14V001",
        "blocked_edge_ids": "GM_RM017_WGV12M002;GM_RM017_WGV12M003;GM_RM017_WGV12M004",
        "context_edge_ids": "GM_RM017_WGV14C001;GM_RM017_WGV14C002;GM_RM017_WGV14C003",
        "confidence": "medium",
        "auto_applied": "yes",
        "needs_user_spotcheck": "yes",
        "visual_summary": "White box truck/van remains visible before and after an intervening black-car selection, but the object is far and partly occluded by street furniture.",
        "rule_triggered": "A;B;G",
        "evidence_frames": [118, 145, 148, 156, 157],
    },
    {
        "wgv1_4_thread_id": "GM_RM017_WGV14T002",
        "scene_id": "GM_RM017",
        "target_family_ids": [
            "GM_RM017_WGV12TF003",
            "GM_RM017_WGV12TF007",
            "GM_RM017_WGV12TF009",
            "GM_RM017_WGV12TF011",
            "GM_RM017_WGV12TF012",
        ],
        "wgv1_4_status": "weak",
        "visual_identity_label": "GM_RM017_black_sedan_interleaved_149_214",
        "same_vehicle_edge_ids": "GM_RM017_WGV14V002;GM_RM017_WGV14V003;GM_RM017_WGV14V004;GM_RM017_WGV12M010",
        "blocked_edge_ids": "GM_RM017_WGV12M002;GM_RM017_WGV12M003;GM_RM017_WGV12M006;GM_RM017_WGV12M007;GM_RM017_WGV12M008;GM_RM017_WGV12M009",
        "context_edge_ids": "GM_RM017_WGV14C001;GM_RM017_WGV14C002;GM_RM017_WGV14C004;GM_RM017_WGV14C005;GM_RM017_WGV14C006;GM_RM017_WGV14C007",
        "confidence": "medium",
        "auto_applied": "yes",
        "needs_user_spotcheck": "yes",
        "visual_summary": "Black sedan appears in interleaved fragments around the white SUV; the 181 to 200 bridge is visually plausible but weak.",
        "rule_triggered": "A;F;G",
        "evidence_frames": [149, 155, 169, 173, 176, 181, 200, 214],
    },
    {
        "wgv1_4_thread_id": "GM_RM017_WGV14T003",
        "scene_id": "GM_RM017",
        "target_family_ids": [
            "GM_RM017_WGV12TF005",
            "GM_RM017_WGV12TF006",
            "GM_RM017_WGV12TF008",
            "GM_RM017_WGV12TF010",
        ],
        "wgv1_4_status": "weak",
        "visual_identity_label": "GM_RM017_white_suv_interleaved_158_185",
        "same_vehicle_edge_ids": "GM_RM017_WGV12M005;GM_RM017_WGV14V005;GM_RM017_WGV14V006",
        "blocked_edge_ids": "GM_RM017_WGV12M004;GM_RM017_WGV12M006;GM_RM017_WGV12M007;GM_RM017_WGV12M008;GM_RM017_WGV12M009",
        "context_edge_ids": "GM_RM017_WGV14C003;GM_RM017_WGV14C004;GM_RM017_WGV14C005;GM_RM017_WGV14C006;GM_RM017_WGV14C007",
        "confidence": "medium_high",
        "auto_applied": "yes",
        "needs_user_spotcheck": "yes",
        "visual_summary": "White SUV fragments are the same vehicle, interleaved with black sedan selections; M005 primary-box issue is resolved as same SUV.",
        "rule_triggered": "A;F;G",
        "evidence_frames": [158, 164, 168, 174, 175, 182, 185],
    },
]


EDGE_OVERRIDES = {
    "GM_RM011_WGV12M001": ("accepted", "same_vehicle_edge_upgraded", "M001 side-window gap remains same white car.", "A;B"),
    "GM_RM011_WGV12M002": ("accepted", "same_vehicle_edge_upgraded", "M002 blocked boundary is visually continuous between frames 9 and 10.", "B;F"),
    "GM_RM011_WGV12M003": ("accepted", "same_vehicle_edge_upgraded", "M003 primary-box issue is duplicate/better-box on same white car.", "D;G"),
    "GM_RM011_WGV12M004": ("accepted", "same_vehicle_edge_upgraded", "M004 continues the same white car from side crop to hood/front crop.", "B"),
    "GM_RM011_WGV12M005": ("context_only", "temporal_context_edge_added", "M005 is same-color replacement from right-side white car to another front-facing white car.", "D;F"),
    "GM_RM011_WGV12M006": ("accepted", "same_vehicle_edge_upgraded", "M006 is same white car with edge-visible truncation.", "B;G"),
    "GM_RM011_WGV12M007": ("accepted", "same_vehicle_edge_upgraded", "M007 missing edge frames, but thread frames 231-233 show the same white car continuing.", "B"),
    "GM_RM011_WGV12M008": ("accepted", "same_vehicle_edge_upgraded", "M008 keeps the same underpass white car through frames 233-239.", "B"),
    "GM_RM011_WGV12M009": ("accepted", "same_vehicle_edge_upgraded", "M009 missing edge frames, but 239 to 242 remains the same white car front.", "B"),
    "GM_RM011_WGV12M010": ("accepted", "same_vehicle_edge_upgraded", "M010 joins frame 249 to 250 as the same white car hood/front-window crop.", "B"),
    "GM_RM011_WGV12M011": ("accepted", "same_vehicle_edge_upgraded", "M011 joins frame 250 to 251 as the same white car side-window crop.", "B"),
    "GM_RM011_WGV12M012": ("accepted", "same_vehicle_edge_upgraded", "M012 joins frames 259 and 260 as the same white car side/rear crop.", "B"),
    "GM_RM011_WGV12M013": ("accepted", "same_vehicle_edge_upgraded", "M013 joins 264 to 265 as the same white car tail/side crop.", "B"),
    "GM_RM011_WGV12M014": ("accepted", "same_vehicle_edge_upgraded", "M014 keeps the same white car through rear/side frames 265-270.", "B"),
    "GM_RM011_WGV12M015": ("accepted", "same_vehicle_edge_upgraded", "M015 keeps the same white car through 269-288; later left SUV is only a competitor.", "B;F;G"),
    "GM_RM011_WGV12M016": ("context_only", "temporal_context_edge_added", "M016 switches from right-side white car to left white SUV competitor.", "D;F;G"),
    "GM_RM017_WGV12M001": ("weak", "same_vehicle_edge_downgraded", "M001 follows a far/partly occluded white box truck; keep weak.", "B"),
    "GM_RM017_WGV12M002": ("context_only", "temporal_context_edge_added", "M002 is white box truck to black sedan.", "D;G"),
    "GM_RM017_WGV12M003": ("context_only", "temporal_context_edge_added", "M003 is black sedan to white box truck.", "D;G"),
    "GM_RM017_WGV12M004": ("context_only", "temporal_context_edge_added", "M004 is white box truck to white SUV, different vehicles.", "D;F"),
    "GM_RM017_WGV12M005": ("weak", "same_vehicle_edge_downgraded", "M005 is the same white SUV but with strong black-car/box-truck competition.", "F;G"),
    "GM_RM017_WGV12M006": ("context_only", "temporal_context_edge_added", "M006 is white SUV to black sedan.", "D;G"),
    "GM_RM017_WGV12M007": ("context_only", "temporal_context_edge_added", "M007 is black sedan to white SUV.", "D;G"),
    "GM_RM017_WGV12M008": ("context_only", "temporal_context_edge_added", "M008 is white SUV to black sedan.", "D;G"),
    "GM_RM017_WGV12M009": ("context_only", "temporal_context_edge_added", "M009 is black sedan to white SUV.", "D;G"),
    "GM_RM017_WGV12M010": ("accepted", "same_vehicle_edge_upgraded", "M010 is the same black sedan over frames 200-214.", "A"),
}


NEW_VISUAL_EDGES = [
    ("GM_RM017_WGV14V001", "GM_RM017", "GM_RM017_WGV12TF002", "GM_RM017_WGV12TF004", "weak", "fragment_merge", "White box truck reappears after intervening black-sedan selection.", "118;145;148;156;157", "A;B;G", "yes"),
    ("GM_RM017_WGV14V002", "GM_RM017", "GM_RM017_WGV12TF003", "GM_RM017_WGV12TF007", "weak", "fragment_merge", "Black sedan remains visible through the white-SUV interleave.", "149;155;169;173", "A;G", "yes"),
    ("GM_RM017_WGV14V003", "GM_RM017", "GM_RM017_WGV12TF007", "GM_RM017_WGV12TF009", "accepted", "fragment_merge", "Black sedan continues from 173 to 176-181 after a brief white-SUV selection.", "169;173;176;181", "A;G", "yes"),
    ("GM_RM017_WGV14V004", "GM_RM017", "GM_RM017_WGV12TF009", "GM_RM017_WGV12TF011", "weak", "fragment_merge", "Black sedan at right edge plausibly continues into 200-214, but the gap is long.", "176;181;200;214", "A;F", "yes"),
    ("GM_RM017_WGV14V005", "GM_RM017", "GM_RM017_WGV12TF006", "GM_RM017_WGV12TF008", "weak", "fragment_merge", "White SUV continues through frames 168 to 174-175 with black-car competition.", "164;168;174;175", "F;G", "yes"),
    ("GM_RM017_WGV14V006", "GM_RM017", "GM_RM017_WGV12TF008", "GM_RM017_WGV12TF010", "weak", "fragment_merge", "White SUV continues from 174-175 to 182-185 after interleaved black-car frames.", "174;175;182;185", "F;G", "yes"),
]


CONTEXT_EDGE_DEFS = [
    ("GM_RM011_WGV14C001", "GM_RM011", "GM_RM011_WGV12M005", "GM_RM011_WGV14T001", "GM_RM011_WGV14T002", "same_frame_competition", "White-car replacement; right near-field car is not the front-facing white car.", "18;24;25;31;32;35", "D;F", "no"),
    ("GM_RM011_WGV14C002", "GM_RM011", "GM_RM011_WGV12M016", "GM_RM011_WGV14T005", "GM_RM011_WGV14T006", "same_frame_competition", "Left white SUV competitor appears at 286-288 and becomes selected at 289.", "286;287;288;289;290;292", "D;F;G", "no"),
    ("GM_RM017_WGV14C001", "GM_RM017", "GM_RM017_WGV12M002", "GM_RM017_WGV14T001", "GM_RM017_WGV14T002", "different_vehicle_context", "White box truck to black sedan, not same vehicle.", "145;148;149;155", "D;G", "no"),
    ("GM_RM017_WGV14C002", "GM_RM017", "GM_RM017_WGV12M003", "GM_RM017_WGV14T002", "GM_RM017_WGV14T001", "different_vehicle_context", "Black sedan to white box truck, with the black sedan still a separate context vehicle.", "149;155;156;157", "D;G", "no"),
    ("GM_RM017_WGV14C003", "GM_RM017", "GM_RM017_WGV12M004", "GM_RM017_WGV14T001", "GM_RM017_WGV14T003", "different_vehicle_context", "White box truck to white SUV; same color family is not identity evidence.", "156;157;158;164", "D;F", "no"),
    ("GM_RM017_WGV14C004", "GM_RM017", "GM_RM017_WGV12M006", "GM_RM017_WGV14T003", "GM_RM017_WGV14T002", "same_frame_competition", "White SUV and black sedan compete in the same frames.", "164;168;169;173", "D;G", "no"),
    ("GM_RM017_WGV14C005", "GM_RM017", "GM_RM017_WGV12M007", "GM_RM017_WGV14T002", "GM_RM017_WGV14T003", "same_frame_competition", "Black sedan to white SUV is interleaved context, not same vehicle.", "169;173;174;175", "D;G", "no"),
    ("GM_RM017_WGV14C006", "GM_RM017", "GM_RM017_WGV12M008", "GM_RM017_WGV14T003", "GM_RM017_WGV14T002", "same_frame_competition", "White SUV to black sedan is interleaved context.", "174;175;176;181", "D;G", "no"),
    ("GM_RM017_WGV14C007", "GM_RM017", "GM_RM017_WGV12M009", "GM_RM017_WGV14T002", "GM_RM017_WGV14T003", "same_frame_competition", "Black sedan to white SUV is interleaved context.", "176;181;182;185", "D;G", "no"),
]


SPOTCHECK_ITEMS = [
    ("SPOT001", "GM_RM011", "high_risk_accepted_change", "GM_RM011_WGV14T005", "high", "accepted_with_spotcheck", "Large WGV1.3 over-split repair across 231-288; many upgraded boundaries lacked edge-review PNGs and frame 286-288 has a competitor white SUV.", "231;233;242;250;259;270;279;288", "yes"),
    ("SPOT002", "GM_RM011", "disputed_context_relation", "GM_RM011_WGV14C002/GM_RM011_WGV12M016", "medium", "context_only", "Confirm that 289-292 left white SUV is not the right-side white car from 279-288.", "286;287;288;289;290;292", "yes"),
    ("SPOT003", "GM_RM017", "weak_merge_needing_spotcheck", "GM_RM017_WGV14T001", "medium", "weak", "White box truck weak merge across an intervening black-car selection and heavy distance/occlusion.", "118;145;148;156;157", "yes"),
    ("SPOT004", "GM_RM017", "weak_merge_needing_spotcheck", "GM_RM017_WGV14T002", "high", "weak", "Black sedan thread is interleaved with white-SUV selections and has a long 181-200 weak bridge.", "149;155;169;173;176;181;200;214", "yes"),
    ("SPOT005", "GM_RM017", "weak_merge_needing_spotcheck", "GM_RM017_WGV14T003", "high", "weak", "White SUV thread is interleaved with black-sedan selections; M005 primary-box issue resolved but remains high-risk.", "158;164;168;174;175;182;185", "yes"),
    ("SPOT006", "ALL", "sar_blocking_unresolved_item", "WGV1.4_WORKING_GRAPH", "high", "blocked", "No WGV1.4 item is SAR-ready; all outputs remain diagnostic working graph only.", "", "no"),
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def split_ids(value: str) -> list[str]:
    return [part for part in value.split(";") if part]


def join_ids(values: list[str]) -> str:
    return ";".join(values)


def rel(path_value: str) -> str:
    return path_value.replace("\\", "/")


def build_indexes(
    frames: list[dict[str, str]],
    edge_frames: list[dict[str, str]],
    splits: list[dict[str, str]],
    threads: list[dict[str, str]],
) -> tuple[dict[str, list[dict[str, str]]], dict[str, list[dict[str, str]]], dict[str, dict[str, str]], dict[str, dict[str, str]]]:
    frames_by_tf: dict[str, list[dict[str, str]]] = {}
    for row in frames:
        frames_by_tf.setdefault(row["target_family_id"], []).append(row)

    edge_frames_by_edge: dict[str, list[dict[str, str]]] = {}
    for row in edge_frames:
        edge_frames_by_edge.setdefault(row["edge_id"], []).append(row)

    split_by_tf = {row["target_family_id"]: row for row in splits}
    thread_by_id = {row["wgv1_3_thread_id"]: row for row in threads}
    return frames_by_tf, edge_frames_by_edge, split_by_tf, thread_by_id


def evidence_paths_for_tfs(
    target_family_ids: list[str],
    frames_by_tf: dict[str, list[dict[str, str]]],
    frame_ids: list[int] | None = None,
    limit: int = 8,
) -> str:
    wanted = {str(fid) for fid in frame_ids or []}
    out: list[str] = []
    for tfid in target_family_ids:
        for row in sorted(frames_by_tf.get(tfid, []), key=lambda r: int(r["frame_id"])):
            if wanted and row["frame_id"] not in wanted:
                continue
            path = row.get("image_path_yolo", "")
            if path and path not in out:
                out.append(rel(path))
            if len(out) >= limit:
                return join_ids(out)
    return join_ids(out)


def evidence_paths_for_edge(
    edge_id: str,
    edge_frames_by_edge: dict[str, list[dict[str, str]]],
    fallback_tfs: list[str],
    frames_by_tf: dict[str, list[dict[str, str]]],
    fallback_frame_ids: list[int] | None = None,
    limit: int = 8,
) -> str:
    out: list[str] = []
    for row in sorted(edge_frames_by_edge.get(edge_id, []), key=lambda r: int(r["frame_id"] or -1)):
        path = row.get("image_path_yolo_annotated", "")
        if path and row.get("copy_status") == "copied" and path not in out:
            out.append(rel(path))
        if len(out) >= limit:
            return join_ids(out)
    if out:
        return join_ids(out)
    return evidence_paths_for_tfs(fallback_tfs, frames_by_tf, fallback_frame_ids, limit=limit)


def thread_old_ids(target_family_ids: list[str], split_by_tf: dict[str, dict[str, str]]) -> list[str]:
    seen: list[str] = []
    for tfid in target_family_ids:
        tid = split_by_tf[tfid]["wgv1_3_thread_id"]
        if tid not in seen:
            seen.append(tid)
    return seen


def source_fragment_ids(target_family_ids: list[str], split_by_tf: dict[str, dict[str, str]]) -> list[str]:
    seen: list[str] = []
    for tfid in target_family_ids:
        fid = split_by_tf[tfid]["source_fragment_id"]
        if fid not in seen:
            seen.append(fid)
    return seen


def frame_span(target_family_ids: list[str], split_by_tf: dict[str, dict[str, str]]) -> tuple[int, int]:
    starts = [int(split_by_tf[tfid]["frame_start"]) for tfid in target_family_ids]
    ends = [int(split_by_tf[tfid]["frame_end"]) for tfid in target_family_ids]
    return min(starts), max(ends)


def make_thread_rows(
    frames_by_tf: dict[str, list[dict[str, str]]],
    split_by_tf: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    rows = []
    for item in WGV14_THREADS:
        tfids = item["target_family_ids"]
        start, end = frame_span(tfids, split_by_tf)
        rows.append(
            {
                "wgv1_4_thread_id": item["wgv1_4_thread_id"],
                "scene_id": item["scene_id"],
                "wgv1_4_status": item["wgv1_4_status"],
                "visual_identity_label": item["visual_identity_label"],
                "old_wgv1_3_thread_ids": join_ids(thread_old_ids(tfids, split_by_tf)),
                "target_family_ids": join_ids(tfids),
                "source_fragment_ids": join_ids(source_fragment_ids(tfids, split_by_tf)),
                "frame_start": str(start),
                "frame_end": str(end),
                "target_family_count": str(len(tfids)),
                "same_vehicle_edge_ids": item["same_vehicle_edge_ids"],
                "blocked_edge_ids": item["blocked_edge_ids"],
                "context_edge_ids": item["context_edge_ids"],
                "confidence": item["confidence"],
                "auto_applied": item["auto_applied"],
                "needs_user_spotcheck": item["needs_user_spotcheck"],
                "sar_ready": NO_SAR,
                "not_final_box_flag": "yes",
                "not_gt_box_flag": "yes",
                "not_revised_annotation_flag": "yes",
                "visual_evidence_frames": join_ids([str(v) for v in item["evidence_frames"]]),
                "visual_evidence_paths": evidence_paths_for_tfs(tfids, frames_by_tf, item["evidence_frames"]),
                "visual_summary": item["visual_summary"],
                "rule_triggered": item["rule_triggered"],
            }
        )
    return rows


def make_fragment_rows(
    frames_by_tf: dict[str, list[dict[str, str]]],
    split_by_tf: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    thread_for_tf = {}
    status_for_tf = {}
    for item in WGV14_THREADS:
        for tfid in item["target_family_ids"]:
            thread_for_tf[tfid] = item["wgv1_4_thread_id"]
            status_for_tf[tfid] = item["wgv1_4_status"]
    rows = []
    for tfid in sorted(split_by_tf, key=lambda k: (split_by_tf[k]["scene_id"], int(split_by_tf[k]["frame_start"]), k)):
        src = split_by_tf[tfid]
        paths = evidence_paths_for_tfs([tfid], frames_by_tf, limit=4)
        rows.append(
            {
                "wgv1_4_fragment_id": tfid.replace("WGV12TF", "WGV14F"),
                "scene_id": src["scene_id"],
                "wgv1_4_thread_id": thread_for_tf[tfid],
                "target_family_id": tfid,
                "old_wgv1_3_thread_id": src["wgv1_3_thread_id"],
                "source_fragment_id": src["source_fragment_id"],
                "frame_start": src["frame_start"],
                "frame_end": src["frame_end"],
                "frame_count": src["frame_count"],
                "wgv1_4_fragment_status": status_for_tf[tfid],
                "class_sequence": src["class_sequence"],
                "x_bin_sequence": src["x_bin_sequence"],
                "visual_evidence_paths": paths,
                "sar_ready": NO_SAR,
                "not_final_box_flag": "yes",
                "not_gt_box_flag": "yes",
                "not_revised_annotation_flag": "yes",
                "note": "WGV1.4 visual working-graph fragment; diagnostic only.",
            }
        )
    return rows


def make_same_edge_rows(
    merges: list[dict[str, str]],
    edge_frames_by_edge: dict[str, list[dict[str, str]]],
    frames_by_tf: dict[str, list[dict[str, str]]],
) -> list[dict[str, str]]:
    rows = []
    for row in merges:
        edge_id = row["merge_candidate_id"]
        status, action, reason, rule = EDGE_OVERRIDES[edge_id]
        final_kind = "same_vehicle" if status in {"accepted", "weak"} else "not_same_vehicle_context"
        fallback_tfs = [row["from_target_family_id"], row["to_target_family_id"]]
        fallback_frames = [int(row["from_frame_end"]), int(row["to_frame_start"])]
        rows.append(
            {
                "edge_id": edge_id,
                "scene_id": row["scene_id"],
                "edge_source": "wgv1_3_candidate",
                "from_target_family_id": row["from_target_family_id"],
                "to_target_family_id": row["to_target_family_id"],
                "from_frame_end": row["from_frame_end"],
                "to_frame_start": row["to_frame_start"],
                "wgv1_3_edge_decision": row["wgv1_3_edge_decision"],
                "wgv1_4_edge_kind": final_kind,
                "wgv1_4_edge_status": status,
                "repair_action": action,
                "confidence": "high" if status == "accepted" else "medium",
                "visual_evidence_frames": f"{row['from_frame_end']};{row['to_frame_start']}",
                "visual_evidence_paths": evidence_paths_for_edge(edge_id, edge_frames_by_edge, fallback_tfs, frames_by_tf, fallback_frames),
                "reason": reason,
                "rule_triggered": rule,
                "auto_applied": "yes",
                "needs_user_spotcheck": "yes" if status == "weak" else "no",
                "sar_ready": NO_SAR,
                "not_final_box_flag": "yes",
                "not_gt_box_flag": "yes",
                "not_revised_annotation_flag": "yes",
            }
        )
    for edge_id, scene, from_tf, to_tf, status, action, reason, frames, rule, spotcheck in NEW_VISUAL_EDGES:
        frame_ids = [int(v) for v in split_ids(frames)]
        rows.append(
            {
                "edge_id": edge_id,
                "scene_id": scene,
                "edge_source": "wgv1_4_visual_added",
                "from_target_family_id": from_tf,
                "to_target_family_id": to_tf,
                "from_frame_end": "",
                "to_frame_start": "",
                "wgv1_3_edge_decision": "not_present",
                "wgv1_4_edge_kind": "same_vehicle",
                "wgv1_4_edge_status": status,
                "repair_action": action,
                "confidence": "medium_high" if status == "accepted" else "medium",
                "visual_evidence_frames": frames,
                "visual_evidence_paths": evidence_paths_for_tfs([from_tf, to_tf], frames_by_tf, frame_ids),
                "reason": reason,
                "rule_triggered": rule,
                "auto_applied": "yes",
                "needs_user_spotcheck": spotcheck,
                "sar_ready": NO_SAR,
                "not_final_box_flag": "yes",
                "not_gt_box_flag": "yes",
                "not_revised_annotation_flag": "yes",
            }
        )
    return rows


def make_context_rows(
    frames_by_tf: dict[str, list[dict[str, str]]],
    split_by_tf: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    tfids_by_thread = {item["wgv1_4_thread_id"]: item["target_family_ids"] for item in WGV14_THREADS}
    rows = []
    for edge_id, scene, source_edge, from_thread, to_thread, ctype, reason, frames, rule, spotcheck in CONTEXT_EDGE_DEFS:
        frame_ids = [int(v) for v in split_ids(frames)]
        tfids = tfids_by_thread[from_thread] + tfids_by_thread[to_thread]
        rows.append(
            {
                "context_edge_id": edge_id,
                "scene_id": scene,
                "source_edge_id": source_edge,
                "from_wgv1_4_thread_id": from_thread,
                "to_wgv1_4_thread_id": to_thread,
                "from_old_wgv1_3_thread_ids": join_ids(thread_old_ids(tfids_by_thread[from_thread], split_by_tf)),
                "to_old_wgv1_3_thread_ids": join_ids(thread_old_ids(tfids_by_thread[to_thread], split_by_tf)),
                "context_type": ctype,
                "wgv1_4_context_status": "context_only",
                "confidence": "high" if spotcheck == "no" else "medium",
                "visual_evidence_frames": frames,
                "visual_evidence_paths": evidence_paths_for_tfs(tfids, frames_by_tf, frame_ids),
                "reason": reason,
                "rule_triggered": rule,
                "auto_applied": "yes",
                "needs_user_spotcheck": spotcheck,
                "sar_ready": NO_SAR,
                "not_final_box_flag": "yes",
                "not_gt_box_flag": "yes",
                "not_revised_annotation_flag": "yes",
            }
        )
    return rows


def make_blocked_rows(
    frames_by_tf: dict[str, list[dict[str, str]]],
) -> list[dict[str, str]]:
    all_tfids = [tfid for item in WGV14_THREADS for tfid in item["target_family_ids"]]
    rows = []
    for item_id, scene, item_type, related_ids, priority, status, reason, frames, spotcheck in SPOTCHECK_ITEMS:
        frame_ids = [int(v) for v in split_ids(frames)] if frames else None
        scene_tfs = all_tfids if scene == "ALL" else [tfid for tfid in all_tfids if tfid.startswith(scene)]
        rows.append(
            {
                "item_id": item_id,
                "scene_id": scene,
                "item_type": item_type,
                "related_ids": related_ids,
                "priority": priority,
                "wgv1_4_status": status,
                "reason": reason,
                "visual_evidence_frames": frames,
                "visual_evidence_paths": evidence_paths_for_tfs(scene_tfs, frames_by_tf, frame_ids, limit=8) if frames else "",
                "needs_user_spotcheck": spotcheck,
                "sar_ready": NO_SAR,
                "not_final_box_flag": "yes",
                "not_gt_box_flag": "yes",
                "not_revised_annotation_flag": "yes",
                "note": "User spotcheck only; not a request to review all frames.",
            }
        )
    return rows


def make_changelog_rows(
    thread_rows: list[dict[str, str]],
    same_edge_rows: list[dict[str, str]],
    context_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seq = 1

    def add(
        scene_id: str,
        old_thread_id: str,
        old_fragment_ids: str,
        new_thread_ids: str,
        change_type: str,
        evidence_frames: str,
        evidence_paths: str,
        reason: str,
        rule: str,
        confidence: str,
        auto: str,
        spotcheck: str,
        note: str,
    ) -> None:
        nonlocal seq
        rows.append(
            {
                "change_id": f"WGV14CHG{seq:03d}",
                "scene_id": scene_id,
                "old_thread_id": old_thread_id,
                "old_fragment_ids": old_fragment_ids,
                "new_thread_ids": new_thread_ids,
                "change_type": change_type,
                "visual_evidence_frames": evidence_frames,
                "visual_evidence_paths": evidence_paths,
                "reason": reason,
                "rule_triggered": rule,
                "confidence": confidence,
                "auto_applied": auto,
                "needs_user_spotcheck": spotcheck,
                "note": note,
            }
        )
        seq += 1

    for t in thread_rows:
        old_threads = split_ids(t["old_wgv1_3_thread_ids"])
        if len(old_threads) > 1:
            add(
                t["scene_id"],
                t["old_wgv1_3_thread_ids"],
                t["target_family_ids"],
                t["wgv1_4_thread_id"],
                "thread_merge",
                t["visual_evidence_frames"],
                t["visual_evidence_paths"],
                t["visual_summary"],
                t["rule_triggered"],
                t["confidence"],
                "yes",
                t["needs_user_spotcheck"],
                "Visual working-graph merge only; not final annotation.",
            )
        if t["wgv1_4_status"] in {"accepted", "weak"}:
            add(
                t["scene_id"],
                t["old_wgv1_3_thread_ids"],
                t["target_family_ids"],
                t["wgv1_4_thread_id"],
                "status_updated",
                t["visual_evidence_frames"],
                t["visual_evidence_paths"],
                f"Set WGV1.4 thread status to {t['wgv1_4_status']}.",
                t["rule_triggered"],
                t["confidence"],
                "yes",
                t["needs_user_spotcheck"],
                "SAR remains blocked.",
            )

    for edge in same_edge_rows:
        action = edge["repair_action"]
        if action in {"same_vehicle_edge_upgraded", "same_vehicle_edge_downgraded", "fragment_merge"}:
            add(
                edge["scene_id"],
                "",
                f"{edge['from_target_family_id']};{edge['to_target_family_id']}",
                "",
                action,
                edge["visual_evidence_frames"],
                edge["visual_evidence_paths"],
                edge["reason"],
                edge["rule_triggered"],
                edge["confidence"],
                "yes",
                edge["needs_user_spotcheck"],
                f"edge_id={edge['edge_id']}; final_status={edge['wgv1_4_edge_status']}",
            )

    for context in context_rows:
        add(
            context["scene_id"],
            f"{context['from_old_wgv1_3_thread_ids']}->{context['to_old_wgv1_3_thread_ids']}",
            "",
            f"{context['from_wgv1_4_thread_id']}->{context['to_wgv1_4_thread_id']}",
            "temporal_context_edge_added",
            context["visual_evidence_frames"],
            context["visual_evidence_paths"],
            context["reason"],
            context["rule_triggered"],
            context["confidence"],
            "yes",
            context["needs_user_spotcheck"],
            f"context_edge_id={context['context_edge_id']}; type={context['context_type']}",
        )

    for item_id, scene, item_type, related_ids, priority, status, reason, frames, spotcheck in SPOTCHECK_ITEMS:
        if item_type == "sar_blocking_unresolved_item":
            add(
                scene,
                "",
                "",
                related_ids,
                "blocked_item_added",
                frames,
                "",
                reason,
                "boundary_no_sar_ready",
                priority,
                "yes",
                spotcheck,
                f"item_id={item_id}; status={status}",
            )
    return rows


def write_report(
    thread_rows: list[dict[str, str]],
    fragment_rows: list[dict[str, str]],
    same_edge_rows: list[dict[str, str]],
    context_rows: list[dict[str, str]],
    blocked_rows: list[dict[str, str]],
    change_rows: list[dict[str, str]],
    source_threads: list[dict[str, str]],
    frame_rows: list[dict[str, str]],
    edge_frame_rows: list[dict[str, str]],
) -> None:
    source_status_counts = Counter(row["thread_status"] for row in source_threads)
    same_status_counts = Counter(row["wgv1_4_edge_status"] for row in same_edge_rows)
    thread_status_counts = Counter(row["wgv1_4_status"] for row in thread_rows)
    frame_copy_counts = Counter(row["copy_status"] for row in frame_rows)
    edge_frame_copy_counts = Counter(row["copy_status"] for row in edge_frame_rows)
    lines = [
        "# OTY2 YOLO26l WGV1.4 auto visual thread audit and repair",
        "",
        "Date: 2026-07-08",
        "",
        "## Scope and boundaries",
        "",
        "WGV1.4 is a diagnostic visual working graph derived from WGV1.3 PNG review evidence. It is not a final annotation, not GT, not revised annotation, not SAR-ready, and does not enter SAR pairing/support/selector/ranking.",
        "",
        "No outputs images or videos are generated by this script. The visual audit used the existing ignored WGV1.3 PNG pack:",
        "",
        "- `outputs/oty2/y26l_wgv1_3_vehicle_thread_review_20260708/`",
        "",
        "## Audit coverage",
        "",
        f"- thread folders audited: {len(source_threads)}",
        f"- thread frame rows checked through contact sheets / PNG evidence: {len(frame_rows)} ({dict(frame_copy_counts)})",
        f"- edge frame rows checked through contact sheets / PNG evidence: {len(edge_frame_rows)} ({dict(edge_frame_copy_counts)})",
        f"- multi-fragment WGV1.3 threads audited: {sum(1 for row in source_threads if int(row['target_family_count']) > 1)}",
        f"- primary_box_selection_issue threads audited: {source_status_counts.get('same_vehicle_thread_candidate_with_primary_box_selection_issue', 0)}",
        f"- standalone WGV1.3 items audited: {source_status_counts.get('standalone_target_family_after_identity_safe_split', 0)}",
        f"- unique WGV1.3 same/split candidate edges audited: {len(EDGE_OVERRIDES)}",
        "",
        "## Visual rules used",
        "",
        "- A. Detection continuity is not same-vehicle continuity.",
        "- B. Near-field truncation can be same-vehicle evidence when body/window/head/tail parts move continuously.",
        "- C. Abrupt pose changes need intermediate-frame explanation.",
        "- D. Primary-box subject jumps block same-vehicle edges.",
        "- E. Head-to-head or tail-to-head is temporal context, not same-vehicle evidence.",
        "- F. Same-color replacement is not identity evidence without position/motion/occlusion continuity.",
        "- G. Same-frame multi-car competition requires selected-box stability.",
        "",
        "## WGV1.4 working graph outputs",
        "",
        f"- threads: `{THREADS_OUT.relative_to(REPO_ROOT).as_posix()}`",
        f"- fragments: `{FRAGMENTS_OUT.relative_to(REPO_ROOT).as_posix()}`",
        f"- same-vehicle edges: `{SAME_EDGES_OUT.relative_to(REPO_ROOT).as_posix()}`",
        f"- temporal context edges: `{CONTEXT_EDGES_OUT.relative_to(REPO_ROOT).as_posix()}`",
        f"- blocked / spotcheck items: `{BLOCKED_OUT.relative_to(REPO_ROOT).as_posix()}`",
        f"- change log: `{CHANGELOG_OUT.relative_to(REPO_ROOT).as_posix()}`",
        f"- user spotcheck: `{SPOTCHECK.relative_to(REPO_ROOT).as_posix()}`",
        "",
        "## Summary counts",
        "",
        f"- WGV1.4 thread rows: {len(thread_rows)} ({dict(thread_status_counts)})",
        f"- WGV1.4 fragment rows: {len(fragment_rows)}",
        f"- WGV1.4 same-edge rows: {len(same_edge_rows)} ({dict(same_status_counts)})",
        f"- WGV1.4 temporal-context rows: {len(context_rows)}",
        f"- blocked/spotcheck rows: {len(blocked_rows)}",
        f"- change-log rows: {len(change_rows)}",
        "",
        "## Scene decisions",
        "",
        "### GM_RM011",
        "",
        "- Merge `GM_RM011_WGV13T001` + `GM_RM011_WGV13T002` into `GM_RM011_WGV14T001`: frames 0-25 are the same near-field white car. M002 is upgraded from split boundary using thread-frame evidence. M003 primary-box issue is resolved as a duplicate/better-box on the same vehicle.",
        "- Keep `GM_RM011_WGV13T003` separate as `GM_RM011_WGV14T002`: M005 shows same-color replacement, not same vehicle.",
        "- Keep `GM_RM011_WGV13T004` standalone as `GM_RM011_WGV14T003`.",
        "- Keep `GM_RM011_WGV13T005` as accepted `GM_RM011_WGV14T004`: frames 151-166 are one white car with near-field edge truncation.",
        "- Merge `GM_RM011_WGV13T006` through `GM_RM011_WGV13T012` into `GM_RM011_WGV14T005`: frames 231-288 are one underpass near-field white car, with a high-risk competitor near 286-288.",
        "- Keep `GM_RM011_WGV13T013` separate as `GM_RM011_WGV14T006`: it is the left white SUV competitor selected after frame 289.",
        "",
        "### GM_RM017",
        "",
        "- `GM_RM017_WGV14T001` is a weak white box-truck thread: `GM_RM017_WGV13T001` plus `GM_RM017_WGV13T003`; T002 black sedan remains context, not a bridge.",
        "- `GM_RM017_WGV14T002` is a weak black sedan thread: T002, T005, T007, and T009. The 181-200 bridge remains the main spotcheck risk.",
        "- `GM_RM017_WGV14T003` is a weak white SUV thread: T004, T006, and T008. M005 primary-box issue resolves to same white SUV, but black-sedan competition keeps it weak.",
        "- Sequential edges M002-M009 are mostly context-only, because adjacent selected boxes alternate between white box truck, black sedan, and white SUV.",
        "",
        "## Accepted items",
        "",
    ]
    for row in thread_rows:
        if row["wgv1_4_status"] == "accepted":
            lines.append(f"- `{row['wgv1_4_thread_id']}`: {row['visual_summary']}")
    lines.extend(["", "## Weak items", ""])
    for row in thread_rows:
        if row["wgv1_4_status"] == "weak":
            lines.append(f"- `{row['wgv1_4_thread_id']}`: {row['visual_summary']}")
    lines.extend(["", "## Review-required / blocked items", ""])
    for row in blocked_rows:
        lines.append(f"- `{row['item_id']}` `{row['priority']}` `{row['wgv1_4_status']}`: {row['reason']}")
    lines.extend(
        [
            "",
            "## SAR and annotation boundary",
            "",
            "- SAR-ready: no / blocked for all rows.",
            "- final boxes generated: no.",
            "- GT boxes generated: no.",
            "- revised annotation generated: no.",
            "- SAR pairing/support/selector/ranking entered: no.",
            "- outputs images/videos committed: no.",
            "",
        ]
    )
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")


def write_spotcheck(blocked_rows: list[dict[str, str]]) -> None:
    priority_order = {
        "high_risk_accepted_change": 0,
        "weak_merge_needing_spotcheck": 1,
        "disputed_context_relation": 2,
        "primary_box_selection_issue_unresolved": 3,
        "sar_blocking_unresolved_item": 4,
    }
    rows = sorted(blocked_rows, key=lambda r: (priority_order.get(r["item_type"], 99), r["priority"], r["item_id"]))
    lines = [
        "# OTY2 WGV1.4 user spotcheck only",
        "",
        "This is not a request to review every WGV1.3 frame. It lists only low-confidence or high-risk WGV1.4 visual repairs.",
        "",
    ]
    for row in rows:
        lines.extend(
            [
                f"## {row['item_id']} - {row['item_type']}",
                "",
                f"- scene_id: `{row['scene_id']}`",
                f"- related_ids: `{row['related_ids']}`",
                f"- priority: `{row['priority']}`",
                f"- status: `{row['wgv1_4_status']}`",
                f"- reason: {row['reason']}",
                f"- evidence frames: `{row['visual_evidence_frames']}`",
                f"- evidence paths: `{row['visual_evidence_paths']}`",
                f"- SAR-ready: `{row['sar_ready']}`",
                "",
            ]
        )
    SPOTCHECK.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    source_threads = read_csv(THREAD_MANIFEST)
    frame_rows = read_csv(FRAME_MANIFEST)
    edge_frame_rows = read_csv(EDGE_FRAME_MANIFEST)
    split_rows = read_csv(SPLIT_TABLE)
    merge_rows = read_csv(MERGE_TABLE)
    frames_by_tf, edge_frames_by_edge, split_by_tf, _thread_by_id = build_indexes(
        frame_rows, edge_frame_rows, split_rows, source_threads
    )

    thread_rows = make_thread_rows(frames_by_tf, split_by_tf)
    fragment_rows = make_fragment_rows(frames_by_tf, split_by_tf)
    same_edge_rows = make_same_edge_rows(merge_rows, edge_frames_by_edge, frames_by_tf)
    context_rows = make_context_rows(frames_by_tf, split_by_tf)
    blocked_rows = make_blocked_rows(frames_by_tf)
    change_rows = make_changelog_rows(thread_rows, same_edge_rows, context_rows)

    write_csv(
        THREADS_OUT,
        thread_rows,
        [
            "wgv1_4_thread_id",
            "scene_id",
            "wgv1_4_status",
            "visual_identity_label",
            "old_wgv1_3_thread_ids",
            "target_family_ids",
            "source_fragment_ids",
            "frame_start",
            "frame_end",
            "target_family_count",
            "same_vehicle_edge_ids",
            "blocked_edge_ids",
            "context_edge_ids",
            "confidence",
            "auto_applied",
            "needs_user_spotcheck",
            "sar_ready",
            "not_final_box_flag",
            "not_gt_box_flag",
            "not_revised_annotation_flag",
            "visual_evidence_frames",
            "visual_evidence_paths",
            "visual_summary",
            "rule_triggered",
        ],
    )
    write_csv(
        FRAGMENTS_OUT,
        fragment_rows,
        [
            "wgv1_4_fragment_id",
            "scene_id",
            "wgv1_4_thread_id",
            "target_family_id",
            "old_wgv1_3_thread_id",
            "source_fragment_id",
            "frame_start",
            "frame_end",
            "frame_count",
            "wgv1_4_fragment_status",
            "class_sequence",
            "x_bin_sequence",
            "visual_evidence_paths",
            "sar_ready",
            "not_final_box_flag",
            "not_gt_box_flag",
            "not_revised_annotation_flag",
            "note",
        ],
    )
    write_csv(
        SAME_EDGES_OUT,
        same_edge_rows,
        [
            "edge_id",
            "scene_id",
            "edge_source",
            "from_target_family_id",
            "to_target_family_id",
            "from_frame_end",
            "to_frame_start",
            "wgv1_3_edge_decision",
            "wgv1_4_edge_kind",
            "wgv1_4_edge_status",
            "repair_action",
            "confidence",
            "visual_evidence_frames",
            "visual_evidence_paths",
            "reason",
            "rule_triggered",
            "auto_applied",
            "needs_user_spotcheck",
            "sar_ready",
            "not_final_box_flag",
            "not_gt_box_flag",
            "not_revised_annotation_flag",
        ],
    )
    write_csv(
        CONTEXT_EDGES_OUT,
        context_rows,
        [
            "context_edge_id",
            "scene_id",
            "source_edge_id",
            "from_wgv1_4_thread_id",
            "to_wgv1_4_thread_id",
            "from_old_wgv1_3_thread_ids",
            "to_old_wgv1_3_thread_ids",
            "context_type",
            "wgv1_4_context_status",
            "confidence",
            "visual_evidence_frames",
            "visual_evidence_paths",
            "reason",
            "rule_triggered",
            "auto_applied",
            "needs_user_spotcheck",
            "sar_ready",
            "not_final_box_flag",
            "not_gt_box_flag",
            "not_revised_annotation_flag",
        ],
    )
    write_csv(
        BLOCKED_OUT,
        blocked_rows,
        [
            "item_id",
            "scene_id",
            "item_type",
            "related_ids",
            "priority",
            "wgv1_4_status",
            "reason",
            "visual_evidence_frames",
            "visual_evidence_paths",
            "needs_user_spotcheck",
            "sar_ready",
            "not_final_box_flag",
            "not_gt_box_flag",
            "not_revised_annotation_flag",
            "note",
        ],
    )
    write_csv(
        CHANGELOG_OUT,
        change_rows,
        [
            "change_id",
            "scene_id",
            "old_thread_id",
            "old_fragment_ids",
            "new_thread_ids",
            "change_type",
            "visual_evidence_frames",
            "visual_evidence_paths",
            "reason",
            "rule_triggered",
            "confidence",
            "auto_applied",
            "needs_user_spotcheck",
            "note",
        ],
    )
    write_report(
        thread_rows,
        fragment_rows,
        same_edge_rows,
        context_rows,
        blocked_rows,
        change_rows,
        source_threads,
        frame_rows,
        edge_frame_rows,
    )
    write_spotcheck(blocked_rows)

    print(f"wrote {REPORT.relative_to(REPO_ROOT).as_posix()}")
    print(f"wrote {THREADS_OUT.relative_to(REPO_ROOT).as_posix()}")
    print(f"wrote {FRAGMENTS_OUT.relative_to(REPO_ROOT).as_posix()}")
    print(f"wrote {SAME_EDGES_OUT.relative_to(REPO_ROOT).as_posix()}")
    print(f"wrote {CONTEXT_EDGES_OUT.relative_to(REPO_ROOT).as_posix()}")
    print(f"wrote {BLOCKED_OUT.relative_to(REPO_ROOT).as_posix()}")
    print(f"wrote {CHANGELOG_OUT.relative_to(REPO_ROOT).as_posix()}")
    print(f"wrote {SPOTCHECK.relative_to(REPO_ROOT).as_posix()}")


if __name__ == "__main__":
    main()
