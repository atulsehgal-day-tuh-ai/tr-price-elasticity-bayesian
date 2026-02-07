from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd
import re

from reporting.report_data import build_report_payload
from reporting.utils import (
    embed_image_as_img_tag,
    json_for_script_tag,
    read_text,
    replace_all,
    write_text,
)


def generate_statistical_report(
    results: Any,
    data: pd.DataFrame,
    output_dir: str,
    *,
    template_path: Optional[str] = None,
) -> str:
    """
    Generate Statistical Validation Report (contract §2).

    Writes: {output_dir}/statistical_validation_report.html
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    if template_path is None:
        template_path = str(Path("mock_references") / "statistical_report_v3.html")
    template_file = Path(template_path)

    # Generate plots (PNG) in output_dir, then embed as base64
    plot_img_tags: Dict[str, str] = {}
    try:
        from visualizations import plot_trace, plot_posteriors, plot_seasonal_patterns, plot_time_trend
        import matplotlib.pyplot as plt

        # File size controls: cap DPI and use JPEG for heavy plots.
        DPI = 120

        trace_path = out / "trace_plot.jpg"
        plot_trace(results, output_path=None)
        plt.savefig(trace_path, dpi=DPI, bbox_inches="tight", format="jpg")
        plt.close()
        plot_img_tags["trace_plot"] = embed_image_as_img_tag(trace_path, alt="MCMC trace plot")

        posterior_path = out / "posterior_plot.jpg"
        plot_posteriors(results, output_path=None)
        plt.savefig(posterior_path, dpi=DPI, bbox_inches="tight", format="jpg")
        plt.close()
        plot_img_tags["posterior_plot"] = embed_image_as_img_tag(posterior_path, alt="Posterior distributions")

        seasonal_path = out / "seasonal_plot.png"
        plot_seasonal_patterns(results, data, output_path=None)
        plt.savefig(seasonal_path, dpi=DPI, bbox_inches="tight")
        plt.close()
        plot_img_tags["seasonal_plot"] = embed_image_as_img_tag(seasonal_path, alt="Seasonality")

        # Optional time trend
        if getattr(results, "beta_time_trend", None) is not None:
            time_trend_path = out / "time_trend_plot.png"
            fig = plot_time_trend(results, data, output_path=None)
            if fig is not None:
                plt.savefig(time_trend_path, dpi=DPI, bbox_inches="tight")
                plt.close()
                plot_img_tags["time_trend_plot"] = embed_image_as_img_tag(time_trend_path, alt="Time trend")
    except Exception:
        # Plotting should never fail report generation; template placeholders will remain.
        plot_img_tags = {}

    payload = build_report_payload(results, data, include_plots=bool(plot_img_tags), plot_img_tags=plot_img_tags)

    # Read base template and inject data + small JS hooks.
    tpl = read_text(template_file)

    # Inject REPORT JSON as application/json right before the existing <script> block.
    # (This keeps templates close to mock_reference while enabling runtime population.)
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

    # Replace hardcoded COEFFICIENTS object with the payload-driven one.
    # We rely on the comment nearby in the mock template.
    tpl = tpl.replace(
        "    // Posterior means (will be injected by Python in production)",
        "    // Posterior means (injected by pipeline)",
    )
    # v3 hook: set interactive constants from REPORT (contract §5).
    hook = (
        "\n    const REPORT = JSON.parse(document.getElementById('report-data').textContent);\n"
        "    const COEFFICIENTS = REPORT.coefficients;\n"
        "    const CROSS_ELASTICITY = (REPORT.summaries && REPORT.summaries.cross && REPORT.summaries.cross.Overall) ? Number(REPORT.summaries.cross.Overall.mean) : 0.0;\n"
        "    const CROSS_HDI = (REPORT.summaries && REPORT.summaries.cross && REPORT.summaries.cross.Overall)\n"
        "        ? [Number(REPORT.summaries.cross.Overall.ci_lower), Number(REPORT.summaries.cross.Overall.ci_upper)]\n"
        "        : [0.0, 0.0];\n"
        "    const SEASON_BETA = {\n"
        "        winter: 0.0,\n"
        "        spring: (REPORT.seasonal && REPORT.seasonal.Spring) ? Number(REPORT.seasonal.Spring.mean) : 0.0,\n"
        "        summer: (REPORT.seasonal && REPORT.seasonal.Summer) ? Number(REPORT.seasonal.Summer.mean) : 0.0,\n"
        "        fall:   (REPORT.seasonal && REPORT.seasonal.Fall)   ? Number(REPORT.seasonal.Fall.mean)   : 0.0\n"
        "    };\n"
        "    const BETA_TIME = (REPORT.beta_time && REPORT.beta_time.mean !== undefined) ? Number(REPORT.beta_time.mean) : 0.0;\n"
        "    const ANNUAL_EROSION_PCT = (Math.exp(BETA_TIME * 52) - 1) * 100;\n"
    )

    # Remove the original hardcoded COEFFICIENTS literal (best-effort, bounded).
    tpl = re.sub(
        r"const\s+COEFFICIENTS\s*=\s*\{[\s\S]*?\};",
        "/* COEFFICIENTS injected by pipeline */",
        tpl,
        count=1,
    )

    # Remove other hardcoded v3 constants that must be injected (best-effort, bounded).
    tpl = re.sub(
        r"const\s+CROSS_ELASTICITY\s*=\s*.*?;",
        "/* CROSS_ELASTICITY injected by pipeline */",
        tpl,
        count=1,
    )
    tpl = re.sub(
        r"const\s+CROSS_HDI\s*=\s*\[[\s\S]*?\];",
        "/* CROSS_HDI injected by pipeline */",
        tpl,
        count=1,
    )
    tpl = re.sub(
        r"const\s+SEASON_BETA\s*=\s*\{[\s\S]*?\};",
        "/* SEASON_BETA injected by pipeline */",
        tpl,
        count=1,
    )
    tpl = re.sub(
        r"const\s+BETA_TIME\s*=\s*.*?;",
        "/* BETA_TIME injected by pipeline */",
        tpl,
        count=1,
    )
    tpl = re.sub(
        r"const\s+ANNUAL_EROSION_PCT\s*=\s*.*?;",
        "/* ANNUAL_EROSION_PCT injected by pipeline */",
        tpl,
        count=1,
    )

    # Inject REPORT-derived constants after removing template hardcodes.
    if "const REPORT =" not in tpl:
        tpl = tpl.replace(marker, marker + hook, 1)

    # Add a small DOM population script for key tables + plots.
    population_js = """
    (function populateStatReport() {
      const REPORT = JSON.parse(document.getElementById('report-data').textContent);

      function fmt1(x) { return (x === null || x === undefined) ? '—' : Number(x).toFixed(1); }
      function fmtPct1(x) { if (x === null || x === undefined) return '—'; const v = Number(x); return (v>=0?'+':'') + v.toFixed(1) + '%'; }
      function fmtProb0(p) { if (p === null || p === undefined) return '—'; return Math.round(Number(p) * 100) + '%'; }

      // Replace plot placeholders by injecting <img> tags if available.
      const plotMap = (REPORT.plots || {});
      const placeholders = document.querySelectorAll('.plot-placeholder');
      placeholders.forEach(ph => {
        const txt = (ph.textContent || '').toLowerCase();
        if ((txt.includes('trace_plot.png') || txt.includes('trace_plot.jpg')) && plotMap.trace_plot) ph.innerHTML = plotMap.trace_plot;
        if ((txt.includes('posterior_plot.png') || txt.includes('posterior_plot.jpg')) && plotMap.posterior_plot) ph.innerHTML = plotMap.posterior_plot;
        if (txt.includes('seasonal_plot.png') && plotMap.seasonal_plot) ph.innerHTML = plotMap.seasonal_plot;
        if (txt.includes('time_trend_plot.png') && plotMap.time_trend_plot) ph.innerHTML = plotMap.time_trend_plot;
      });

      // Convergence verdict banner text (best-effort; template has example copy).
      const diag = REPORT.diagnostics || {};
      const verdict = (diag.converged === true) ? 'Pass' : (diag.converged === false ? 'Fail' : '—');
      const banners = document.querySelectorAll('.verdict-banner');
      banners.forEach(b => {
        b.querySelectorAll('.vb-status').forEach(x => x.textContent = verdict);
        b.querySelectorAll('.vb-metric').forEach(x => {
          const t = (x.textContent || '');
          if (t.toLowerCase().includes('r-hat')) x.textContent = (diag.rhat_max !== null && diag.rhat_max !== undefined) ? diag.rhat_max.toFixed(3) : '—';
          if (t.toLowerCase().includes('ess')) x.textContent = (diag.ess_min !== null && diag.ess_min !== undefined) ? Math.round(diag.ess_min).toString() : '—';
          if (t.toLowerCase().includes('diverg')) x.textContent = (diag.n_divergences !== null && diag.n_divergences !== undefined) ? diag.n_divergences.toString() : '—';
        });
      });

      // Tables used across sections
      const tables = Array.from(document.querySelectorAll('table'));

      // Fill convergence diagnostics table (Section 02) by header signature.
      const convTable = tables.find(t => (t.querySelector('thead')?.innerText || '').includes('ESS (Bulk)') && (t.querySelector('thead')?.innerText || '').includes('R-hat') && (t.querySelector('thead')?.innerText || '').includes('Status') && (t.querySelector('thead')?.innerText || '').includes('Parameter'));
      if (convTable) {
        const tbody = convTable.querySelector('tbody');
        if (tbody) {
          const rows = [];
          const drows = REPORT.diagnostic_rows || [];

          function badge(rhat, essb, divs) {
            const okR = (rhat === null || rhat === undefined) ? true : (Number(rhat) < 1.01);
            const okE = (essb === null || essb === undefined) ? true : (Number(essb) > 400);
            const okD = (divs === null || divs === undefined) ? true : (Number(divs) === 0);
            if (okR && okE && okD) return '<span class="badge badge-pass">Pass</span>';
            if (okR && okE) return '<span class="badge badge-warn">Warn</span>';
            return '<span class="badge badge-fail">Fail</span>';
          }

          function fmtInt(x) { return (x === null || x === undefined) ? '—' : Math.round(Number(x)).toLocaleString(); }

          // Simple grouping by parameter name prefix
          function groupName(p) {
            if (p.startsWith('mu_global_base') || p.startsWith('base_elasticity') || p.startsWith('sigma_group_base')) return 'Hierarchical — Base Price Elasticity';
            if (p.startsWith('mu_global_promo') || p.startsWith('promo_elasticity') || p.startsWith('sigma_group_promo')) return 'Hierarchical — Promotional Elasticity';
            if (p.startsWith('beta_') || p.startsWith('elasticity_cross') || p === 'sigma') return 'Shared Parameters';
            return 'Other';
          }

          const grouped = {};
          drows.forEach(r => {
            const p = String(r.param || '');
            const g = groupName(p);
            grouped[g] = grouped[g] || [];
            grouped[g].push(r);
          });

          const order = ['Hierarchical — Base Price Elasticity','Hierarchical — Promotional Elasticity','Shared Parameters','Other'];
          order.forEach(g => {
            const arr = grouped[g] || [];
            if (!arr.length) return;
            rows.push(`<tr class="table-group-header"><td colspan="5">${g}</td></tr>`);
            arr.forEach(r => {
              const p = String(r.param || '');
              rows.push(
                '<tr>' +
                `<td class="row-label">${p}</td>` +
                `<td>${(r.rhat === null || r.rhat === undefined) ? '—' : Number(r.rhat).toFixed(3)}</td>` +
                `<td>${fmtInt(r.ess_bulk)}</td>` +
                `<td>${fmtInt(r.ess_tail)}</td>` +
                `<td>${badge(r.rhat, r.ess_bulk, null)}</td>` +
                '</tr>'
              );
            });
          });

          // Divergences row if available
          if (diag.n_divergences !== null && diag.n_divergences !== undefined) {
            rows.push('<tr class="table-group-header"><td colspan="5">Sampler Health</td></tr>');
            const badgeDiv = (Number(diag.n_divergences) === 0) ? '<span class="badge badge-pass">Pass</span>' : '<span class="badge badge-warn">Review</span>';
            rows.push(
              '<tr>' +
              '<td class="row-label">Divergent transitions</td>' +
              `<td colspan="3" style="color: var(--warn); font-weight: 600;">${diag.n_divergences} divergences</td>` +
              `<td>${badgeDiv}</td>` +
              '</tr>'
            );
          }

          tbody.innerHTML = rows.join('\\n');
        }
      }

      // Fill the base elasticity table (4a) by finding the table with headers matching P(elastic).
      const baseTable = tables.find(t => (t.querySelector('thead')?.innerText || '').includes('P(elastic)') && (t.querySelector('thead')?.innerText || '').includes('1% Price Increase'));
      if (baseTable) {
        const tbody = baseTable.querySelector('tbody');
        if (tbody) {
          const rows = [];
          const order = REPORT.retailers || [];
          order.forEach((nm) => {
            const s = (REPORT.summaries?.base || {})[nm];
            const p = (REPORT.probabilities?.base || {})[nm];
            if (!s) return;
            const cls = (nm === 'Overall') ? 'overall-row' : '';
            const mean = Number(s.mean);
            const sd = Number(s.sd);
            const hdi = '[' + fmt1(s.ci_lower) + ', ' + fmt1(s.ci_upper) + ']';
            const pneg = fmtProb0(p?.p_negative);
            const pel = fmtProb0(p?.p_elastic_abs_gt_1);
            const impact = fmtPct1(mean * 1.0);
            rows.push(`<tr class=\"${cls}\"><td class=\"row-label\">${nm}</td><td class=\"${mean<0?'num-negative':'num-positive'}\">${fmt1(mean)}</td><td>${fmt1(sd)}</td><td>${hdi}</td><td>${pneg}</td><td>${pel}</td><td style=\"font-family:var(--sans);font-size:12px;\">${impact} volume impact</td></tr>`);
          });
          tbody.innerHTML = rows.join('\\n');
        }
      }

      // Fill promo table if present (4b) by header β_promo.
      const promoTable = tables.find(t => (t.querySelector('thead')?.innerText || '').includes('β_promo') && (t.querySelector('thead')?.innerText || '').includes('Promo'));
      if (promoTable) {
        const tbody = promoTable.querySelector('tbody');
        if (tbody) {
          const rows = [];
          const order = REPORT.retailers || [];
          order.forEach((nm) => {
            const s = (REPORT.summaries?.promo || {})[nm];
            if (!s) return;
            const cls = (nm === 'Overall') ? 'overall-row' : '';
            const mean = Number(s.mean);
            const sd = Number(s.sd);
            const hdi = '[' + fmt1(s.ci_lower) + ', ' + fmt1(s.ci_upper) + ']';
            const pneg = fmtProb0((REPORT.probabilities?.promo || {})[nm]?.p_negative);
            // 1pp deeper discount (depth=-0.01)
            const impact = (Math.exp(mean * -0.01) - 1) * 100;
            rows.push(`<tr class=\"${cls}\"><td class=\"row-label\">${nm}</td><td class=\"${mean<0?'num-negative':'num-positive'}\">${fmt1(mean)}</td><td>${fmt1(sd)}</td><td>${hdi}</td><td>${pneg}</td><td style=\"font-family:var(--sans);font-size:12px;\">${fmtPct1(impact)} volume impact</td></tr>`);
          });
          tbody.innerHTML = rows.join('\\n');
        }
      }

      // Availability table (if present) - match header has_promo/has_competitor
      const availTable = tables.find(t => (t.querySelector('thead')?.innerText || '').includes('has_promo') && (t.querySelector('thead')?.innerText || '').includes('has_competitor'));
      if (availTable) {
        const tbody = availTable.querySelector('tbody');
        if (tbody) {
          const rows = [];
          (REPORT.availability || []).forEach(r => {
            rows.push(`<tr><td>${r.Retailer}</td><td>${r.has_promo ?? ''}</td><td>${r.has_competitor ?? ''}</td></tr>`);
          });
          tbody.innerHTML = rows.join('\\n');
        }
      }
    })();
    """

    # Append population JS before the LAST </script> (avoid touching the report-data script tag).
    if population_js.strip() not in tpl and "</script>" in tpl:
        head, tail = tpl.rsplit("</script>", 1)
        tpl = head + population_js + "\n</script>" + tail

    report_path = out / "statistical_validation_report.html"
    write_text(report_path, tpl)
    return str(report_path)

