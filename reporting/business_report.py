from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, List

import re
import numpy as np
import pandas as pd

from reporting.report_data import build_report_payload
from reporting.utils import (
    embed_image_as_img_tag,
    fmt1,
    fmt_pct1,
    json_for_script_tag,
    pill_html,
    read_text,
    write_text,
)


def _compute_business_findings(payload: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Generate key findings rows using contract-style conditional templates.
    This is intentionally simple/templated (LLM enhancement downstream).
    """
    out: List[Dict[str, str]] = []
    coeff = payload.get("coefficients", {})
    base = coeff.get("base", {})
    promo = coeff.get("promo", {})
    cross = coeff.get("cross", {})
    beta_time = payload.get("beta_time")

    # 1) Base elasticity overall
    b = base.get("Overall")
    if b is not None:
        if abs(float(b)) > 1:
            out.append({"finding": "Demand is elastic — any base price increase reduces revenue", "applies": "Overall", "p": "0.95"})
        else:
            out.append({"finding": "Demand is inelastic — modest price increases may grow revenue", "applies": "Overall", "p": "0.80"})

    # 2) Promo/Base ratio overall
    if b is not None and promo.get("Overall") is not None:
        ratio = abs(float(promo["Overall"])) / max(abs(float(b)), 1e-9)
        out.append(
            {
                "finding": f"Promotions are {ratio:.1f}× more effective than base price changes",
                "applies": "Overall",
                "p": "0.90",
            }
        )

    # 3) Time trend alert
    if beta_time is not None:
        annual = float(beta_time.get("annual_pct_mean", 0.0))
        if annual <= -2.0:
            out.append({"finding": f"Underlying demand declining {annual:.1f}% annually", "applies": "All retailers (shared)", "p": "0.95"})
        elif annual >= 2.0:
            out.append({"finding": f"Underlying demand growing {annual:.1f}% annually", "applies": "All retailers (shared)", "p": "0.80"})

    # 4) Cross-price note
    if cross.get("Overall") is not None:
        out.append({"finding": "Private Label pricing has directional impact on SI volume (review HDI)", "applies": "BJ's, Sam's Club", "p": "0.60"})

    return out


def _build_headline_cards(payload: Dict[str, Any]) -> str:
    """
    Build the 4×3 headline card grid section (contract §3 headline cards).
    """
    retailers = payload.get("retailers", [])
    coeff = payload.get("coefficients", {})
    base = coeff.get("base", {})
    promo = coeff.get("promo", {})
    beta_time = payload.get("beta_time")

    # Confidence for base uses P(negative) as directional certainty (proxy).
    pbase = payload.get("probabilities", {}).get("base", {})
    ppromo = payload.get("probabilities", {}).get("promo", {})

    def card(metric_label: str, value_html: str, sub_html: str, color_cls: str, overall: bool) -> str:
        overall_cls = " hcard-overall" if overall else ""
        return (
            f'<div class="hcard {color_cls}{overall_cls}">'
            f'<div class="hc-label">{metric_label}</div>'
            f'<div class="hc-val">{value_html}</div>'
            f'<div class="hc-sub">{sub_html}</div>'
            f"</div>"
        )

    def row_label(title: str, tag: str, tag_cls: str) -> str:
        return (
            f'<div class="cards-row-label">{title} '
            f'<span class="row-tag {tag_cls}">{tag}</span></div>'
        )

    rows = []

    # Overall row
    rows.append(row_label("Overall", "GLOBAL ESTIMATE", "row-tag-overall"))
    b = base.get("Overall")
    p = promo.get("Overall") if promo else None
    ratio = (abs(float(p)) / max(abs(float(b)), 1e-9)) if (b is not None and p is not None) else None

    base_p = pbase.get("Overall", {}).get("p_negative") if isinstance(pbase, dict) else None
    promo_p = ppromo.get("Overall", {}).get("p_negative") if isinstance(ppromo, dict) else None

    base_pill = pill_html(base_p)
    promo_pill = pill_html(promo_p) if p is not None else pill_html(None)
    trend_pill = pill_html(0.95, shared=True) if beta_time is not None else pill_html(None, shared=True)

    annual = float(beta_time.get("annual_pct_mean")) if beta_time else None
    annual_txt = fmt_pct1(annual) if annual is not None else "—"

    grid = ['<div class="headline-grid">']
    grid.append(
        card(
            "Price Sensitivity",
            f"{fmt1(b)}" if b is not None else "—",
            f"{base_pill} 1% base price ↑ → {fmt_pct1(float(b) * 1.0) if b is not None else '—'} volume impact",
            "hc-red",
            True,
        )
    )
    grid.append(
        card(
            "Promo Power",
            f"{ratio:.1f}×" if ratio is not None else "—",
            f"{promo_pill} Promo/Base ratio",
            "hc-green",
            True,
        )
    )
    grid.append(
        card(
            "Demand Trend",
            annual_txt,
            f"{trend_pill} Annualized β_time trend (shared)",
            "hc-amber",
            True,
        )
    )
    grid.append("</div>")
    rows.append("".join(grid))

    # Retailer rows
    for r in retailers:
        if r == "Overall":
            continue
        rows.append(row_label(r, "RETAILER", "row-tag-retailer"))
        bb = base.get(r, b)
        pp = promo.get(r, p) if promo else None
        rr = (abs(float(pp)) / max(abs(float(bb)), 1e-9)) if (bb is not None and pp is not None) else None
        bp = pbase.get(r, {}).get("p_negative") if isinstance(pbase, dict) else None
        pr = ppromo.get(r, {}).get("p_negative") if isinstance(ppromo, dict) else None
        base_pill_r = pill_html(bp, shared=(r != "Overall" and (payload.get("model_type") != "Hierarchical")))
        promo_pill_r = pill_html(pr, shared=(r != "Overall" and (payload.get("model_type") != "Hierarchical"))) if pp is not None else pill_html(None)
        trend_pill_r = pill_html(0.95, shared=True) if beta_time is not None else pill_html(None, shared=True)

        grid = ['<div class="headline-grid">']
        grid.append(
            card(
                "Price Sensitivity",
                f"{fmt1(bb)}" if bb is not None else "—",
                f"{base_pill_r} 1% base price ↑ → {fmt_pct1(float(bb) * 1.0) if bb is not None else '—'} volume impact",
                "hc-red",
                False,
            )
        )
        grid.append(
            card(
                "Promo Power",
                f"{rr:.1f}×" if rr is not None else "—",
                f"{promo_pill_r} Promo/Base ratio",
                "hc-green",
                False,
            )
        )
        grid.append(
            card(
                "Demand Trend",
                annual_txt,
                f"{trend_pill_r} Shared estimate",
                "hc-amber",
                False,
            )
        )
        grid.append("</div>")
        rows.append("".join(grid))

    return "\n".join(rows)


def _build_evidence_table(payload: Dict[str, Any]) -> str:
    rows = []
    for r in payload.get("evidence", [])[:200]:
        match = r.get("Match", "")
        cls = "td-green" if match == "Close" else ("td-amber" if match == "Directional" else "td-red")
        rows.append(
            "<tr>"
            f'<td class="td-label">{r.get("Retailer","")}</td>'
            f'<td>{r.get("Date","")}</td>'
            f'<td class="{cls}">{fmt_pct1(r.get("Price_Move_Pct"))}</td>'
            f'<td class="{cls}">{fmt_pct1(r.get("Observed_Vol_Impact_Pct"))}</td>'
            f'<td class="{cls}">{fmt_pct1(r.get("Predicted_Vol_Impact_Pct"))}</td>'
            f'<td class="{cls}">{match}</td>'
            "</tr>"
        )
    return "\n".join(rows) if rows else '<tr><td class="td-muted" colspan="6">No qualifying price moves found (or insufficient before/after window).</td></tr>'


def _replace_first_tbody_after(tpl: str, anchor: str, new_tbody: str) -> str:
    """
    Replace the first <tbody>...</tbody> after an anchor substring.
    """
    i = tpl.find(anchor)
    if i == -1:
        return tpl
    j = tpl.find("<tbody>", i)
    if j == -1:
        return tpl
    k = tpl.find("</tbody>", j)
    if k == -1:
        return tpl
    return tpl[: j + len("<tbody>")] + "\n" + new_tbody + "\n" + tpl[k:]


def _scenario_lookup(payload: Dict[str, Any], kind: str) -> Dict[tuple, Dict[str, Any]]:
    out = {}
    for row in (payload.get("scenarios", {}) or {}).get(kind, []) or []:
        key = (row.get("Retailer"), row.get("price_change_pct") if kind == "base" else row.get("discount_depth_pct"))
        out[key] = row
    return out


def _build_base_overall_rows(payload: Dict[str, Any]) -> str:
    m = _scenario_lookup(payload, "base")
    rows = []
    for pct in [-5, -3, -1, 1, 3, 5]:
        r = m.get(("Overall", float(pct)))
        if not r:
            continue
        vol = float(r["volume_impact_mean"])
        rev = float(r["revenue_impact_mean"])
        cls_v = "td-green" if vol >= 0 else "td-red"
        cls_r = "td-green" if rev >= 0 else "td-red"
        conf = pill_html(float(r.get("probability_positive", 0.0)))
        label = f"{pct:+.0f}%".replace("+", "+").replace("-", "−")
        rows.append(
            f'<tr><td class="td-label">{label}</td>'
            f'<td class="{cls_v}">{fmt_pct1(vol)}</td>'
            f'<td class="{cls_r}">{fmt_pct1(rev)}</td>'
            f"<td>{conf}</td></tr>"
        )
    return "\n".join(rows)


def _build_base_by_retailer_rows(payload: Dict[str, Any]) -> str:
    m = _scenario_lookup(payload, "base")
    coeff = payload.get("coefficients", {}).get("base", {})
    retailers = payload.get("retailers", [])

    # Rank by |elasticity| (exclude Overall)
    vals = [(r, abs(float(coeff.get(r)))) for r in retailers if r != "Overall" and coeff.get(r) is not None]
    vals_sorted = sorted(vals, key=lambda x: x[1])
    least = vals_sorted[0][0] if vals_sorted else None
    most = vals_sorted[-1][0] if vals_sorted else None

    def rel_label(r: str) -> str:
        if r == "Overall":
            return "—"
        if r == least:
            return "Least sensitive"
        if r == most:
            return "Most sensitive"
        return "Mid-range"

    def rel_style(r: str) -> str:
        if r == least:
            return ' style="font-family:var(--sans);font-size:12px;color:var(--green);"'
        if r == most:
            return ' style="font-family:var(--sans);font-size:12px;color:var(--red);"'
        return ' style="font-family:var(--sans);font-size:12px;"'

    rows = []
    for r in retailers:
        b = coeff.get(r)
        if b is None:
            continue
        scen = m.get((r, 1.0))
        vol = float(scen["volume_impact_mean"]) if scen else float(b) * 1.0
        rev = float(scen["revenue_impact_mean"]) if scen else ((1 + vol / 100) * (1 + 0.01) - 1) * 100
        conf = pill_html(float(scen.get("probability_positive", 0.0))) if scen else pill_html(None)
        cls_v = "td-green" if vol >= 0 else "td-red"
        cls_r = "td-green" if rev >= 0 else "td-red"
        tr_cls = "overall-row" if r == "Overall" else ""
        rows.append(
            f'<tr class="{tr_cls}"><td class="td-label">{r}</td>'
            f"<td>{fmt1(b)}</td>"
            f'<td class="{cls_v}">{fmt_pct1(vol)}</td>'
            f'<td class="{cls_r}">{fmt_pct1(rev)}</td>'
            f"<td>{conf}</td>"
            f"<td{rel_style(r)}>{rel_label(r)}</td></tr>"
        )
    return "\n".join(rows)


def _build_base_bar_section(payload: Dict[str, Any]) -> str:
    coeff = payload.get("coefficients", {}).get("base", {})
    retailers = [r for r in payload.get("retailers", []) if r != "Overall"]
    vals = [(r, float(coeff.get(r))) for r in retailers if coeff.get(r) is not None]
    if not vals:
        return ""
    max_abs = max(abs(v) for _, v in vals) or 1.0
    # Width scaled to 80% max like contract suggests.
    def width(v: float) -> float:
        return min(80.0, abs(v) / max_abs * 80.0)

    # Color scheme: least sensitive blue, most sensitive red, others purple.
    vals_sorted = sorted(vals, key=lambda x: abs(x[1]))
    least = vals_sorted[0][0]
    most = vals_sorted[-1][0]

    rows = []
    for r, v in vals_sorted:
        color = "var(--blue)" if r == least else ("var(--red)" if r == most else "var(--purple)")
        note = "Least sensitive" if r == least else ("Most sensitive" if r == most else "")
        rows.append(
            '<div class="bar-row">'
            f'<div class="bar-label">{r}</div>'
            f'<div class="bar-track"><div class="bar-fill" style="width:{width(v):.1f}%;background:{color};">{fmt_pct1(v)}</div></div>'
            f'<div class="bar-note">{note}</div>'
            "</div>"
        )

    return (
        '<div class="bar-section">'
        '<div class="bar-section-title">Volume Impact of 1% Base Price Increase — By Retailer</div>'
        + "\n".join(rows)
        + "</div>"
    )


def _build_promo_overall_rows(payload: Dict[str, Any]) -> str:
    m = _scenario_lookup(payload, "promo")
    rows = []
    for disc in [5, 10, 15, 20]:
        r = m.get(("Overall", float(disc)))
        if not r:
            continue
        vol = float(r["volume_impact_mean"])
        rev = float(r["revenue_impact_mean"])
        rpp = rev / float(disc) if disc else 0.0
        cls_v = "td-green" if vol >= 0 else "td-red"
        cls_r = "td-green" if rev >= 0 else "td-red"
        cls_rpp = "td-green" if rpp >= 0 else "td-red"
        conf = pill_html(float(r.get("probability_positive", 0.0)))
        rows.append(
            f'<tr><td class="td-label">{disc:.0f}% off</td>'
            f'<td class="{cls_v}">{fmt_pct1(vol)}</td>'
            f'<td class="{cls_r}">{fmt_pct1(rev)}</td>'
            f'<td class="{cls_rpp}">{fmt_pct1(rpp, signed=False)}</td>'
            f"<td>{conf}</td></tr>"
        )
    return "\n".join(rows)


def _build_promo_by_retailer_rows(payload: Dict[str, Any]) -> str:
    m_base = _scenario_lookup(payload, "base")
    m_promo = _scenario_lookup(payload, "promo")
    base = payload.get("coefficients", {}).get("base", {})
    promo = payload.get("coefficients", {}).get("promo", {})
    retailers = payload.get("retailers", [])
    rows = []
    for r in retailers:
        if promo.get(r) is None:
            continue
        p = float(promo[r])
        b = float(base.get(r)) if base.get(r) is not None else None
        scen = m_promo.get((r, 10.0))
        vol = float(scen["volume_impact_mean"]) if scen else (np.exp(p * -0.10) - 1) * 100
        rev = float(scen["revenue_impact_mean"]) if scen else ((1 + vol / 100) * (1 - 0.10) - 1) * 100
        ratio = abs(p) / max(abs(b), 1e-9) if b is not None else None
        conf = pill_html(float(scen.get("probability_positive", 0.0))) if scen else pill_html(None)
        cls_v = "td-green" if vol >= 0 else "td-red"
        cls_r = "td-green" if rev >= 0 else "td-red"
        tr_cls = "overall-row" if r == "Overall" else ""
        ratio_html = f"{ratio:.1f}×" if ratio is not None else "—"
        rows.append(
            f'<tr class="{tr_cls}"><td class="td-label">{r}</td>'
            f"<td>{fmt1(p)}</td>"
            f'<td class="{cls_v}">{fmt_pct1(vol, signed=False)}</td>'
            f'<td class="{cls_r}">{fmt_pct1(rev)}</td>'
            f"<td>{ratio_html}</td>"
            f"<td>{conf}</td></tr>"
        )
    return "\n".join(rows)


def _build_promo_bar_section(payload: Dict[str, Any]) -> str:
    m = _scenario_lookup(payload, "promo")
    retailers = [r for r in payload.get("retailers", []) if r != "Overall"]
    vals = []
    for r in retailers:
        scen = m.get((r, 10.0))
        if scen:
            vals.append((r, float(scen["volume_impact_mean"])))
    if not vals:
        return ""
    max_abs = max(abs(v) for _, v in vals) or 1.0
    def width(v: float) -> float:
        return min(90.0, abs(v) / max_abs * 90.0)
    vals_sorted = sorted(vals, key=lambda x: -x[1])
    most = vals_sorted[0][0]
    least = vals_sorted[-1][0]
    rows = []
    for r, v in vals_sorted:
        color = "var(--green)" if r != least else "var(--blue)"
        note = "Most responsive" if r == most else ("Least responsive" if r == least else "")
        rows.append(
            '<div class="bar-row">'
            f'<div class="bar-label">{r}</div>'
            f'<div class="bar-track"><div class="bar-fill" style="width:{width(v):.1f}%;background:{color};">{fmt_pct1(v, signed=False)}</div></div>'
            f'<div class="bar-note">{note}</div>'
            "</div>"
        )
    return (
        '<div class="bar-section">'
        '<div class="bar-section-title">Volume Impact of 10% Discount — By Retailer</div>'
        + "\n".join(rows)
        + "</div>"
    )


def _build_cross_rows(payload: Dict[str, Any]) -> str:
    cross_s = (payload.get("summaries", {}) or {}).get("cross", {})
    c_over = cross_s.get("Overall")
    if not c_over:
        return ""
    mean = float(c_over["mean"])
    ci_l = float(c_over["ci_lower"])
    ci_u = float(c_over["ci_upper"])
    # Confidence: HDI excludes 0 => high, else low.
    excludes = (ci_l > 0 and ci_u > 0) or (ci_l < 0 and ci_u < 0)
    conf = pill_html(0.95 if excludes else 0.6)

    # Determine masking by has_competitor flags
    has_comp = {}
    for row in payload.get("availability", []) or []:
        has_comp[str(row.get("Retailer"))] = row.get("has_competitor")

    rows = []
    retailers = payload.get("retailers", [])
    for r in retailers:
        if r != "Overall" and has_comp.get(r) == 0:
            rows.append(
                f'<tr><td class="td-label">{r}</td><td class="td-muted">— masked (no PL data)</td>'
                f'<td class="td-muted">N/A</td><td><span class="pill pill-na">N/A</span></td></tr>'
            )
            continue
        label = "Overall" if r == "Overall" else f"{fmt1(mean)} (shared)"
        impact = fmt_pct1(mean * 1.0)
        rows.append(
            f'<tr class=\"{"overall-row" if r=="Overall" else ""}\">'
            f'<td class="td-label">{r}</td><td>{fmt1(mean) if r=="Overall" else label}</td>'
            f'<td class="td-muted">{impact} (directional)</td><td>{conf}</td></tr>'
        )
    return "\n".join(rows)


def _build_season_grid(payload: Dict[str, Any]) -> str:
    seasonal = payload.get("seasonal", {}) or {}
    # Contract: winter baseline.
    def season_cell(name: str, val: str, sub: str, cls: str) -> str:
        return (
            f'<div class="season-cell {cls}"><div class="s-name">{name}</div>'
            f'<div class="s-val">{val}</div><div class="s-sub">{sub}</div></div>'
        )
    cells = []
    cells.append(season_cell("Winter", "Baseline", "Dec – Feb", "s-winter"))
    for s, months, cls in [("Spring", "Mar – May", "s-spring"), ("Summer", "Jun – Aug", "s-summer"), ("Fall", "Sep – Nov", "s-fall")]:
        if s not in seasonal:
            continue
        b = seasonal[s]
        pct = (np.exp(float(b["mean"])) - 1) * 100.0
        ci_l = float(b["ci_lower"])
        ci_u = float(b["ci_upper"])
        excludes = (ci_l > 0 and ci_u > 0) or (ci_l < 0 and ci_u < 0)
        pill = pill_html(0.95 if excludes else 0.6, shared=True)
        cells.append(season_cell(s, fmt_pct1(pct, signed=False), f"{months} · {pill}", cls))
    return '<div class="season-grid">' + "\n".join(cells) + "</div>"


def _build_trend_alert(payload: Dict[str, Any]) -> str:
    bt = payload.get("beta_time")
    if not bt:
        return ""
    mean = float(bt.get("annual_pct_mean", 0.0))
    lo = float(bt.get("annual_pct_ci_lower", 0.0))
    hi = float(bt.get("annual_pct_ci_upper", 0.0))
    # 3-year cumulative range from annual CI bounds (contract v3)
    def cum3(pct: float) -> float:
        return ((1 + pct / 100.0) ** 3 - 1) * 100.0

    cum3_mean = cum3(mean)
    cum3_lo = cum3(lo)
    cum3_hi = cum3(hi)
    cum3_min = min(cum3_lo, cum3_hi)
    cum3_max = max(cum3_lo, cum3_hi)
    icon = "🚨"
    cls = "alert-red" if mean < 0 else "alert"
    return (
        f'<div class="alert {cls}">'
        f'<div class="alert-icon">{icon}</div>'
        f'<div class="alert-text">Organic demand is {"declining" if mean<0 else "growing"} '
        f'<strong>{fmt_pct1(mean)}</strong> annually (95% range: {fmt_pct1(lo)} to {fmt_pct1(hi)}), '
        f'after controlling for price, promotions, and seasonality. This is a shared estimate '
        f'across all retailers. Over 3 years, the cumulative baseline shift is approximately '
        f'<strong>{fmt_pct1(cum3_min)} to {fmt_pct1(cum3_max)}</strong> '
        f'(mean: {fmt_pct1(cum3_mean)}).</div></div>'
    )


def generate_business_report(
    results: Any,
    data: pd.DataFrame,
    output_dir: str,
    *,
    template_path: Optional[str] = None,
) -> str:
    """
    Generate Business Decision Brief (contract §3).

    Writes: {output_dir}/business_decision_brief.html
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    if template_path is None:
        template_path = str(Path("mock_references") / "business_report_v3.html")
    template_file = Path(template_path)

    # Business template is designed to be image-light. Still embed plots if present in output_dir.
    plot_img_tags: Dict[str, str] = {}
    for name in ["time_trend_plot.png", "seasonal_plot.png"]:
        p = out / name
        if p.exists():
            plot_img_tags[name.replace(".png", "")] = embed_image_as_img_tag(p, alt=name)

    payload = build_report_payload(results, data, include_plots=bool(plot_img_tags), plot_img_tags=plot_img_tags)

    tpl = read_text(template_file)

    # Inject REPORT JSON near the bottom before the simulator script.
    marker = "<script>"
    if marker not in tpl:
        raise ValueError("Template missing <script> marker for JS injection.")

    report_json_tag = (
        '\n<script id="report-data" type="application/json">'
        + json_for_script_tag(payload)
        + "</script>\n"
    )
    if 'id="report-data"' not in tpl:
        tpl = tpl.replace(marker, report_json_tag + marker, 1)

    # ---------------------------------------------------------------------
    # v3: Inject JS constants block from REPORT payload (contract §5)
    # ---------------------------------------------------------------------
    # Replace the entire constants prelude (R/ORDER + SEASON + BETA_TIME + CROSS)
    # while keeping the rest of the simulator logic intact.
    constants_start = tpl.find("// ── Retailer elasticities")
    if constants_start == -1:
        constants_start = tpl.find("const R = {")
    constants_end = tpl.find("// ── DOM refs ──", constants_start) if constants_start != -1 else -1
    if constants_start != -1 and constants_end != -1:
        injected_constants = (
            "// ── Retailer elasticities (from posterior means) ──\n"
            "const REPORT = JSON.parse(document.getElementById('report-data').textContent);\n"
            "const R = {\n"
            "  'Overall':    { base: REPORT.coefficients.base['Overall'], promo: (REPORT.coefficients.promo||{})['Overall'] },\n"
            "  \"BJ's\":       { base: REPORT.coefficients.base[\"BJ's\"], promo: (REPORT.coefficients.promo||{})[\"BJ's\"] },\n"
            "  'Costco':     { base: REPORT.coefficients.base['Costco'], promo: (REPORT.coefficients.promo||{})['Costco'] },\n"
            "  \"Sam's Club\": { base: REPORT.coefficients.base[\"Sam's Club\"], promo: (REPORT.coefficients.promo||{})[\"Sam's Club\"] }\n"
            "};\n"
            "const ORDER = ['Overall', \"BJ's\", \"Costco\", \"Sam's Club\"];\n"
            "\n"
            "// ── Seasonal coefficients (from model β_season) ──\n"
            "// These are SHARED across retailers (not hierarchical)\n"
            "function _sb(name) { return (REPORT.seasonal && REPORT.seasonal[name] && REPORT.seasonal[name].mean !== undefined) ? Number(REPORT.seasonal[name].mean) : 0.0; }\n"
            "const SEASON = {\n"
            "  winter: { beta: 0.0000, multiplier: 1.000, maxWeeks: 13, label: 'Winter' },\n"
            "  spring: { beta: _sb('Spring'), multiplier: Math.exp(_sb('Spring')), maxWeeks: 13, label: 'Spring' },\n"
            "  summer: { beta: _sb('Summer'), multiplier: Math.exp(_sb('Summer')), maxWeeks: 13, label: 'Summer' },\n"
            "  fall:   { beta: _sb('Fall'),   multiplier: Math.exp(_sb('Fall')),   maxWeeks: 13, label: 'Fall' }\n"
            "};\n"
            "\n"
            "// ── Demand erosion (from model β_time) ──\n"
            "const BETA_TIME = (REPORT.beta_time && REPORT.beta_time.mean !== undefined) ? Number(REPORT.beta_time.mean) : 0.0;\n"
            "const ANNUAL_EROSION_PCT = (Math.exp(BETA_TIME * 52) - 1) * 100;\n"
            "\n"
            "// ── Cross-price (shared JS block; used by findings + calculators) ──\n"
            "const CROSS = {\n"
            "  mean:  (REPORT.summaries && REPORT.summaries.cross && REPORT.summaries.cross.Overall) ? Number(REPORT.summaries.cross.Overall.mean) : 0.0,\n"
            "  ciLow: (REPORT.summaries && REPORT.summaries.cross && REPORT.summaries.cross.Overall) ? Number(REPORT.summaries.cross.Overall.ci_lower) : 0.0,\n"
            "  ciHigh:(REPORT.summaries && REPORT.summaries.cross && REPORT.summaries.cross.Overall) ? Number(REPORT.summaries.cross.Overall.ci_upper) : 0.0\n"
            "};\n"
            "\n"
            "// ── Update season labels in simulator UI (avoid stale hardcoded % in template) ──\n"
            "function _setSeasonPct(id, beta) {\n"
            "  const el = document.getElementById(id);\n"
            "  if (!el) return;\n"
            "  const pct = (Math.exp(Number(beta)) - 1) * 100;\n"
            "  el.textContent = (pct >= 0 ? '+' : '') + pct.toFixed(1) + '%';\n"
            "}\n"
            "_setSeasonPct('sim-season-spring-mult', SEASON.spring.beta);\n"
            "_setSeasonPct('sim-season-summer-mult', SEASON.summer.beta);\n"
            "_setSeasonPct('sim-season-fall-mult',   SEASON.fall.beta);\n"
            "\n"
        )
        tpl = tpl[:constants_start] + injected_constants + tpl[constants_end:]

    # v3 contract §1.7.6: promote cross-price constants to shared JS block.
    # Remove local constants and update references to CROSS.* inside the findings JS.
    if "const crossMean" in tpl or "crossCILow" in tpl or "crossCIHigh" in tpl:
        tpl = re.sub(r"^[ \t]*const[ \t]+crossMean[ \t]*=.*?;[ \t]*\r?\n", "", tpl, flags=re.MULTILINE)
        tpl = re.sub(r"^[ \t]*const[ \t]+crossCILow[ \t]*=.*?;[ \t]*\r?\n", "", tpl, flags=re.MULTILINE)
        tpl = re.sub(r"^[ \t]*const[ \t]+crossCIHigh[ \t]*=.*?;[ \t]*\r?\n", "", tpl, flags=re.MULTILINE)
        tpl = re.sub(r"\bcrossMean\b", "CROSS.mean", tpl)
        tpl = re.sub(r"\bcrossCILow\b", "CROSS.ciLow", tpl)
        tpl = re.sub(r"\bcrossCIHigh\b", "CROSS.ciHigh", tpl)

    # Add IDs to the simulator season multiplier spans so the injected JS can update them.
    # (Template values are placeholders; production code must be dynamic.)
    tpl = tpl.replace(
        'Spring <span style="font-family:var(--mono);font-size:9px;color:var(--green);">+9.4%</span>',
        'Spring <span id="sim-season-spring-mult" style="font-family:var(--mono);font-size:9px;color:var(--green);">+9.4%</span>',
    )
    tpl = tpl.replace(
        'Summer <span style="font-family:var(--mono);font-size:9px;color:var(--amber);">+21.8%</span>',
        'Summer <span id="sim-season-summer-mult" style="font-family:var(--mono);font-size:9px;color:var(--amber);">+21.8%</span>',
    )
    tpl = tpl.replace(
        'Fall <span style="font-family:var(--mono);font-size:9px;color:var(--purple);">+2.2%</span>',
        'Fall <span id="sim-season-fall-mult" style="font-family:var(--mono);font-size:9px;color:var(--purple);">+2.2%</span>',
    )

    # Replace headline cards section (between the first cards-section div and the divider after it).
    cards_html = _build_headline_cards(payload)
    anchor = "<!-- HEADLINE CARDS: 4 ROWS"
    div_open = '<div class="cards-section">'
    div_end = '</div>\n\n    <div class="divider"></div>'
    a_i = tpl.find(anchor)
    if a_i != -1:
        s_i = tpl.find(div_open, a_i)
        if s_i != -1:
            s_inner = s_i + len(div_open)
            e_i = tpl.find(div_end, s_inner)
            if e_i != -1:
                tpl = tpl[:s_inner] + "\n" + cards_html + "\n" + tpl[e_i:]

    # ---------------------------------------------------------------------
    # Populate key tables/sections with real values (replace mock numbers)
    # ---------------------------------------------------------------------

    # Base price scenario table (Overall)
    tpl = _replace_first_tbody_after(
        tpl,
        '<div class="section-title">Base Price Impact — Overall</div>',
        _build_base_overall_rows(payload),
    )

    # Base by retailer table (1% increase)
    tpl = _replace_first_tbody_after(
        tpl,
        "Base Price Impact — By Retailer",
        _build_base_by_retailer_rows(payload),
    )

    # Base bar visual (replace between the first base \"<!-- Bar visual -->\" and the divider)
    base_section_anchor = '<div class="section-title" style="font-size:17px; margin-top:32px;">Base Price Impact — By Retailer'
    a_i = tpl.find(base_section_anchor)
    if a_i != -1:
        bar_i = tpl.find("<!-- Bar visual -->", a_i)
        div_i = tpl.find('<div class="bar-section">', bar_i)
        end_i = tpl.find("</div>\n    </div>\n\n    <div class=\"divider\"></div>", div_i)
        if bar_i != -1 and div_i != -1 and end_i != -1:
            new_bar = _build_base_bar_section(payload)
            tpl = tpl[:div_i] + new_bar + "\n" + tpl[end_i:]

    # Promo overall table
    tpl = _replace_first_tbody_after(
        tpl,
        '<div class="section-title">Promotional Discount Impact — Overall</div>',
        _build_promo_overall_rows(payload),
    )

    # Promo by retailer (10% discount)
    tpl = _replace_first_tbody_after(
        tpl,
        "Promotional Response — By Retailer",
        _build_promo_by_retailer_rows(payload),
    )

    # Promo bar visual
    promo_section_anchor = '<div class="section-title" style="font-size:17px; margin-top:32px;">Promotional Response — By Retailer'
    a_i = tpl.find(promo_section_anchor)
    if a_i != -1:
        bar_i = tpl.find("<!-- Bar visual -->", a_i)
        div_i = tpl.find('<div class="bar-section">', bar_i)
        end_i = tpl.find("</div>\n    </div>\n\n    <div class=\"divider\"></div>", div_i)
        if bar_i != -1 and div_i != -1 and end_i != -1:
            new_bar = _build_promo_bar_section(payload)
            tpl = tpl[:div_i] + new_bar + "\n" + tpl[end_i:]

    # Cross-price table rows
    cross_rows = _build_cross_rows(payload)
    if cross_rows:
        tpl = _replace_first_tbody_after(
            tpl,
            '<div class="section-title">Private Label Cross-Price Impact</div>',
            cross_rows,
        )

        # Update the cross-price warning banner text (best-effort)
        c = (payload.get("summaries", {}) or {}).get("cross", {}).get("Overall")
        if c:
            mean = float(c["mean"])
            lo = float(c["ci_lower"])
            hi = float(c["ci_upper"])
            includes0 = (lo <= 0 <= hi)
            banner = (
                f"Cross-price elasticity is <strong>{fmt1(mean)}</strong> "
                f"(95% range includes zero: {fmt1(lo)} to {fmt1(hi)}). "
                + ("This effect is <strong>not statistically distinguishable from no effect</strong>. " if includes0 else "This effect is <strong>directionally consistent</strong>. ")
                + "Costco has no Private Label data and is excluded."
            )
            cross_anchor = '<div class="section-title">Private Label Cross-Price Impact</div>'
            ci = tpl.find(cross_anchor)
            if ci != -1:
                at = tpl.find('<div class="alert-text">', ci)
                ae = tpl.find("</div>\n        </div>\n\n        <table>", at)
                if at != -1 and ae != -1:
                    at2 = at + len('<div class="alert-text">')
                    tpl = tpl[:at2] + "\n                " + banner + "\n            " + tpl[ae:]

    # Seasonality grid
    season_anchor = '<div class="section-title">Seasonal Demand Pattern</div>'
    si = tpl.find(season_anchor)
    if si != -1:
        sg = tpl.find('<div class="season-grid">', si)
        # End of season section is divider after it
        div_end = tpl.find("</div>\n\n    <div class=\"divider\"></div>", sg)
        if sg != -1 and div_end != -1:
            # Replace the entire season-grid block (start at <div class=\"season-grid\">)
            tpl = tpl[:sg] + _build_season_grid(payload) + "\n" + tpl[div_end:]

    # Demand trend alert
    trend_anchor = '<div class="section-title">Underlying Demand Decline</div>'
    ti = tpl.find(trend_anchor)
    if ti != -1:
        alert_i = tpl.find('<div class="alert alert-red">', ti)
        alert_end = tpl.find("</div>\n        </div>\n    </div>", alert_i)
        if alert_i != -1 and alert_end != -1:
            tpl = tpl[:alert_i] + _build_trend_alert(payload) + tpl[alert_end:]

    # Evidence table rows: find the evidence table by header signature and replace tbody content.
    # Use simple string markers around the evidence table in the mock (it appears once).
    # Insert evidence scan metadata as a short note above the evidence table.
    em = payload.get("evidence_meta") or {}
    if em and "<div class=\"section-title\">What Happened When Prices Actually Changed?</div>" in tpl:
        note = (
            f"<div class=\"section-desc\" style=\"margin-top:-8px;\">"
            f"Scan rules: |WoW base price % change| &gt; {em.get('pct_threshold', 1.0)}% "
            f"and {em.get('window_weeks', 4)}-week before/after windows. "
            f"Events found: {em.get('events_total', 0)}. "
            f"Qualified: {em.get('events_qualified', 0)}. "
            f"Skipped (insufficient window): {em.get('skipped_insufficient_window', 0)}. "
            f"Skipped (missing/zero values): {em.get('skipped_missing_values', 0)}."
            f"</div>"
        )
        anchor = "<div class=\"section-desc\">"
        # Insert after the existing evidence section desc (first occurrence after title)
        pre, post = tpl.split("<div class=\"section-title\">What Happened When Prices Actually Changed?</div>", 1)
        # re-attach title then insert note after first section-desc close
        if "</div>" in post:
            idx = post.find("</div>") + len("</div>")
            tpl = pre + "<div class=\"section-title\">What Happened When Prices Actually Changed?</div>" + post[:idx] + note + post[idx:]

    if "<th>Price Move (%)</th>" in tpl and "<tbody>" in tpl:
        # Replace the first evidence table body after the header signature.
        pre, post = tpl.split("<th>Price Move (%)</th>", 1)
        # Find the tbody in the remainder
        if "<tbody>" in post and "</tbody>" in post:
            a, b = post.split("<tbody>", 1)
            body, c = b.split("</tbody>", 1)
            new_body = "\n" + _build_evidence_table(payload) + "\n"
            post2 = a + "<tbody>" + new_body + "</tbody>" + c
            tpl = pre + "<th>Price Move (%)</th>" + post2

    # v3: Key Findings are generated in client-side JS from injected constants.
    # Do NOT inject rows from Python; keep <tbody id="findings-body"> empty to avoid duplicates.

    # Footer: update the generation timestamp (best-effort).
    footer_marker = "<div class=\"footer\">"
    if footer_marker in tpl:
        # Overwrite the footer contents with current payload metadata.
        model = payload.get("model_type", "Model")
        nobs = payload.get("n_obs", "—")
        gen = payload.get("generated_at", "")
        new_footer = (
            f'{footer_marker}\n'
            f'  <div>{model} Model · {nobs} obs</div>\n'
            f'  <div>Generated {gen} · 95% Credible Intervals</div>\n'
            f"</div>"
        )
        # Replace the existing footer block (first occurrence)
        # Find end of footer
        pre, rest = tpl.split(footer_marker, 1)
        if "</div>\n\n</div>" in rest:
            # keep the closing container divs; replace until first closing footer div
            # Locate the end of footer (first </div> after footer start)
            end_idx = rest.find("</div>") + len("</div>")
            tpl = pre + new_footer + rest[end_idx:]

    report_path = out / "business_decision_brief.html"
    write_text(report_path, tpl)
    return str(report_path)

