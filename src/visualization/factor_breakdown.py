"""Evidence breakdown view for diagnostic candidates."""

from __future__ import annotations

from pathlib import Path

from .svg_canvas import candidate_rank, compact, esc, first_present, label, normalize_family


def _evidence(row: dict[str, str]) -> dict[str, str]:
    dr = first_present(row, ("delta_r_from_pred",))
    da = first_present(row, ("delta_az_from_pred",))
    dc = first_present(row, ("delta_cross_from_pred",))
    prior = "missing"
    if dr or da or dc:
        prior = f"dr={dr or 'missing'} da={da or 'missing'} dc={dc or 'missing'}"

    family = normalize_family(row)
    mode_rank = first_present(row, ("c1_2_mode_rank",))
    mode_score = first_present(row, ("c1_2_mode_score",))
    mode_text = mode_score or mode_rank
    return {
        "prior consistency": prior,
        "topk support": mode_text if family == "factor_topk" and mode_text else "missing",
        "wedge support": mode_text if family == "wedge" and mode_text else "missing",
        "ray support": mode_text if family == "ray" and mode_text else "missing",
        "signed temporal support": first_present(
            row,
            (
                "signed_direction_match_tracklet_refined",
                "signed_direction_match_refined",
                "signed_direction_match",
                "signed_direction_parity_status",
                "signed_direction_tracklet_parity_status",
            ),
        )
        or "missing",
        "visible risk": first_present(
            row,
            (
                "visible_risk",
                "sar_support_leakage_status",
                "sar_local_background_contrast_status",
                "sar_body_compactness_status",
            ),
        )
        or "missing",
        "conflict score": first_present(row, ("escape_conflict_score", "posterior_margin", "posterior_margin_refined"))
        or "missing",
    }


def render_factor_breakdown(
    sample: dict[str, str],
    candidates: list[dict[str, str]],
    output_path: str | Path,
) -> int:
    cols = [
        ("rank", 70),
        ("family", 160),
        ("candidate_id", 410),
        ("prior consistency", 310),
        ("topk support", 150),
        ("wedge support", 160),
        ("ray support", 150),
        ("signed temporal support", 280),
        ("visible risk", 250),
        ("conflict score", 170),
    ]
    width = sum(col_width for _, col_width in cols) + 80
    row_h = 38
    max_rows = max(1, min(len(candidates), 24))
    height = 200 + row_h * (max_rows + 2)
    body = [
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff" />',
        label(28, 42, f"Factor Breakdown: {sample.get('sample_id')} | {sample.get('sample_type')}", 26),
        label(28, 76, "Missing factors are shown as missing; no synthetic factor values are generated.", 16, "#6b7280"),
        label(28, 100, f"source={sample.get('source_id', '')} | kind={sample.get('source_kind', '')} | fallback_used={sample.get('_fallback_used', 'false')}", 15, "#374151"),
        label(28, 122, "boundary: factor fields are audit context only, not selector or A008 scoring.", 15, "#6b7280"),
    ]
    x = 28
    y = 158
    for title, col_w in cols:
        body.append(f'<rect x="{x}" y="{y - 24}" width="{col_w}" height="30" fill="#f3f4f6" stroke="#e5e7eb" />')
        body.append(label(x + 8, y - 3, title, 14, "#374151"))
        x += col_w
    y += 24

    rows = candidates[:max_rows] if candidates else [{}]
    for idx, row in enumerate(rows, start=1):
        ev = _evidence(row)
        values = {
            "rank": candidate_rank(row, idx) if row else "missing",
            "family": normalize_family(row) if row else "missing",
            "candidate_id": compact(row.get("candidate_id", ""), 54) if row else "missing",
            **ev,
        }
        x = 28
        fill = "#ffffff" if idx % 2 else "#fbfdff"
        for title, col_w in cols:
            value = values.get(title, "missing") or "missing"
            color = "#9ca3af" if value == "missing" else "#111827"
            body.append(f'<rect x="{x}" y="{y - 23}" width="{col_w}" height="{row_h}" fill="{fill}" stroke="#edf2f7" />')
            body.append(label(x + 8, y, compact(value, max(10, col_w // 8)), 13, color))
            x += col_w
        y += row_h

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="Arial, Helvetica, sans-serif">\n'
        + "\n".join(body)
        + "\n</svg>\n"
    )
    Path(output_path).write_text(svg, encoding="utf-8")
    return 1
