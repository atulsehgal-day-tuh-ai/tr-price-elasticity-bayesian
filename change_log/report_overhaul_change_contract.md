# Change Contract (Implemented) — Contract-Driven Two-Report Overhaul (No MCMC Run)

This is a factual record of what was **actually changed** in the repo to implement the contract-driven reporting overhaul based on `contracts/report_specification_contract.md`, plus hardening changes (canonical retailers, explicit evidence-scan rules, report-size controls). No MCMC was executed during this work.

---

## 1) Reporting architecture overhaul (two reports, contract-driven)

### What changed
- Introduced a **new report-generation package** to isolate report logic from the existing large `visualizations.py`, while still **reusing plot utilities**.
- Implemented **two contract-driven HTML reports**:
  - `statistical_validation_report.html`
  - `business_decision_brief.html`

### New report generators (entry points)
- `reporting/statistical_report.py::generate_statistical_report(results, data, output_dir, template_path=None)`
- `reporting/business_report.py::generate_business_report(results, data, output_dir, template_path=None)`

### Files added
- `reporting/__init__.py`
- `reporting/utils.py`
- `reporting/report_data.py`
- `reporting/statistical_report.py`
- `reporting/business_report.py`

---

## 2) Canonical retailer enforcement + explicit missing-retailer rules (hardening)

### Why
The contract requires **Overall + By Retailer everywhere**, and the business expects the 3 retailers:
- BJ’s
- Costco
- Sam’s Club

### What was implemented
- `reporting/report_data.py` enforces a canonical retailer list:
  - `CANONICAL_RETAILERS = ["BJ's", "Costco", "Sam's Club"]`
- Payload always contains:
  - `payload["retailers"] = ["Overall"] + CANONICAL_RETAILERS (+ any extra retailers found in data appended at end)`
- Explicit **SHARED fallback rule**:
  - If hierarchical per-retailer posterior samples exist → use them
  - Else → copy Overall estimate into each retailer row as SHARED fallback (so tables/cards always render)

---

## 3) Historical Evidence Scan: specified + meta counts surfaced (hardening)

### Why
Contract defines a strict methodology and we must handle insufficient history (e.g., newer Costco extracts).

### What was implemented
- `reporting/report_data.py::compute_evidence_table(...)` now returns:
  - `(evidence_rows, evidence_meta)`
- `evidence_meta` includes:
  - `events_total`
  - `events_qualified`
  - `skipped_insufficient_window`
  - `skipped_missing_values`
  - `pct_threshold`
  - `window_weeks`
- Insufficient history handling:
  - Events without enough ±4 weeks are skipped and counted under `skipped_insufficient_window`.
- `reporting/business_report.py` now injects a short “scan rules + counts” note above the evidence table.

---

## 4) Interactive planner approach: preserve template JS, inject only data (hardening)

### Why
Templates already contain substantial inline JS that implements the contract formulas. Rewriting it is risky.

### What was implemented
- Kept template JS intact.
- Injected real coefficients via a JSON payload in the HTML:
  - Business template: replaced hardcoded `const R = {...}` with values derived from injected report JSON (`REPORT.coefficients`).
  - Statistical template: removed the hardcoded `const COEFFICIENTS = {...}` and sets `COEFFICIENTS = REPORT.coefficients`.

This approach minimizes errors and aligns with the contract’s formulas by preserving the template logic.

---

## 5) Report size controls (base64 embedding can get huge) (hardening)

### Why
Base64-embedded images (trace plots, posteriors) can create extremely large HTML files.

### What was implemented
- `reporting/statistical_report.py`:
  - Caps plot DPI at `DPI = 120`
  - Saves heavy plots as **JPEG** before embedding:
    - `trace_plot.jpg`
    - `posterior_plot.jpg`
  - Keeps lighter plots as PNG:
    - `seasonal_plot.png`
    - `time_trend_plot.png` (if available)
- `reporting/utils.py`:
  - Replaced PNG-only embedder with a generic embedder:
    - `embed_image_as_img_tag(path)` supports png/jpg/jpeg/gif/webp and uses correct MIME types.

---

## 6) Wiring changes: pipeline + config + public API

### `visualizations.py`
- Kept plotting utilities.
- `generate_html_report(...)` is now a **legacy wrapper** that generates both reports and returns a dict:
  - `{"statistical_validation_report": "...", "business_decision_brief": "..."}`

- Added new public wrappers:
  - `generate_statistical_report(...)`
  - `generate_business_report(...)`

(Implemented with lazy imports to avoid circular imports because reporting reuses plotting helpers from `visualizations.py`.)

### `run_analysis.py`
- Replaced legacy single-report generation with contract-driven two-report generation.
- Output logs updated to list the two reports and next steps.

### `config_template.yaml`
- Added report flags:
  - `output.generate_statistical_report: true`
  - `output.generate_business_report: true`
- Still honors legacy `output.generate_html` as fallback.

---

## 7) Examples + README updated for the new report behavior

### Updated files
- `README.md`
- `examples/example_01_simple.py`
- `examples/example_02_hierarchical.py`
- `examples/example_04_costco.py`
- `examples/example_05_base_vs_promo.py`
- `examples/example_06_smoke_beta_time_costco.py`

### Behavior change
Examples now treat report generation as returning a dict of two report paths (instead of a single HTML path).

---

## 8) Template sources used

Reports are generated from these mock templates (as sources):
- `mock_references/statistical_report_v2.html`
- `mock_references/business_report_v2.html`

No duplicate copies of templates were created. The generator injects JSON + replaces specific sections/tables programmatically.

---

## 9) Safety / execution constraints honored

- No MCMC or sampling was executed as part of this work.
- Only non-sampling validation was run:
  - `python -m compileall ...`
  - import smoke tests
  - lint checks on edited files

---

## 10) Current git state (important)

These changes are **not committed yet**.

Current working tree includes:
- Modified tracked files:
  - `README.md`
  - `visualizations.py`
  - `run_analysis.py`
  - `config_template.yaml`
  - `examples/*` (01, 02, 04, 05, 06)
- Untracked content:
  - `reporting/`
  - `mock_references/`
  - `contracts/report_specification_contract.md`
  - `.cursor/` (typically should not be committed)

If you want a push, we should stage/commit `reporting/`, `mock_references/`, and the contract file, and exclude `.cursor/` (or add it to `.gitignore`).

