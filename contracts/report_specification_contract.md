# REPORT SPECIFICATION CONTRACT
## Bayesian Price Elasticity Analysis — Sparkling Ice (Club Channel)

**Version:** 1.0  
**Date:** February 7, 2026  
**Prepared by:** Atul (Data Science) + Claude (AI Assistant)  
**Status:** AGREED — Ready for Production Code

---

## 1. SHARED REQUIREMENTS (Both Reports)

### 1.1 Self-Contained HTML
- All images **base64-embedded inline** — zero external file dependencies
- Pattern: `_embed_image(path)` converts PNG to `<img src="data:image/png;base64,{encoded}">`
- One HTML file = complete report, shareable via email / Teams / Slack / Drive
- No separate CSS, JS, or image files

```python
import base64

def _embed_image(path):
    with open(path, 'rb') as f:
        encoded = base64.b64encode(f.read()).decode('utf-8')
    return f'<img src="data:image/png;base64,{encoded}">'
```

### 1.2 Formatting Rules
- **Decimal places:** All displayed numbers use **1 decimal place**. Internal JS computation values may use full precision.
- **Terminology:** "Impact" used everywhere. Never "lift", "gain", "loss", "decline", or "change" interchangeably. Directional sign (+/−) carries the meaning.
- **Overall + By Retailer everywhere:** Every metric shown at Overall level first, then broken out by BJ's, Costco, Sam's Club. **No exceptions.**

### 1.3 Confidence Language (Business Report)
Raw probabilities translated into pills:

| Probability | Label | Color |
|---|---|---|
| 95–100% | HIGH CONFIDENCE | Green |
| 80–94% | MODERATE | Amber |
| 50–79% | LOW | Red |
| Below 50% | NOT RELIABLE | Gray |
| Shared param | SHARED | Gray |

### 1.4 Code Architecture
- Both reports generated from `visualizations.py`
- Two entry points: `generate_statistical_report(results, data, output_dir)` and `generate_business_report(results, data, output_dir)`
- Both consume the same `results` (BayesianResults/HierarchicalResults) + `data` (DataFrame) objects
- Gated by config flags in `config_template.yaml`
- No changes to `data_prep.py`, `bayesian_models.py`, or `run_analysis.py` (except adding the second report call)

### 1.5 Data Objects Available

**From `results`:**
- `results.base_elasticity` (.mean, .ci_lower, .ci_upper)
- `results.promo_elasticity` (same)
- `results.elasticity_cross` (same)
- `results.seasonal_effects` (dict: Spring/Summer/Fall)
- `results.beta_time_trend` (same structure)
- `results.group_elasticities` (dict by retailer — hierarchical only)
- `results.global_elasticity` (hierarchical only)
- `results.revenue_impact(pct)` → dict with volume/revenue impact + probability
- `results.promo_impact(discount)` → same
- `results.base_price_impact(pct)` → same with CI
- `results.trace` (full ArviZ InferenceData)
- `results.converged`, `results.rhat_max`, `results.ess_min`, `results.n_divergences`

**From `data`:**
- Retailer, Date, Volume_Sales_SI, Base_Price_SI, has_promo, has_competitor, Promo_Depth_SI, Price_PL

---

## 2. STATISTICAL VALIDATION REPORT

**Audience:** Data Science team  
**Purpose:** Prove model trustworthiness  
**Theme:** Light mode (IBM Plex Sans / IBM Plex Mono)

### Section 01 — Model Equation

**Equation box:** Full linear predictor with color-coded terms:
- Dependent variable (green): `log(Volume_it)`
- Coefficients (purple): `α_r`, `β_base,r`, `β_promo,r`, `β_cross`, `β_spring`, `β_summer`, `β_fall`, `β_time`
- Masks (gray italic): `has_promo`, `has_competitor`
- Noise (amber): `ε_it`

**Hierarchical structure box:** Shows `β_base,r ~ Normal(μ_base, σ_base)` and `β_promo,r ~ Normal(μ_promo, σ_promo)`

**Term-by-Term Interpretation Grid (3 columns):**

| Term | Scale | Interpretation Rule + 1% Example |
|---|---|---|
| β_base,r | log–log | Direct elasticity. 1% price increase → β_base% volume impact. Ex: β = −1.8 → −1.8% volume impact |
| β_promo,r | log–level (semi-elasticity) | Volume impact = (e^(β × depth) − 1) × 100. Ex: β = −4.2, depth = −0.10 → +53% volume impact |
| β_cross | log–log | Direct cross-elasticity. 1% PL price change → β_cross% SI volume impact. Masked to zero for Costco |
| β_season | log–dummy (vs Winter) | % impact vs Winter = (e^β − 1) × 100. Ex: β_summer = 0.197 → +21.8% volume impact vs Winter |
| β_time | log–level (weekly) | Annualized: (e^(β × 52) − 1) × 100. Ex: β = −0.00090 → −4.6% annual impact |
| has_promo, has_competitor | binary mask | Not estimated. Fixed constants from config. Multiply predictors to zero for missing data |
| α_r | log-level | Baseline log-volume at reference values. Not directly interpretable as business metric |
| σ | log-scale SD | Prediction error ≈ ±(e^σ − 1) × 100%. Ex: σ = 0.42 → ±52% week-to-week deviation |
| σ_base, σ_promo | SD of group effects | Between-retailer spread. Small → strong pooling. Large → weak pooling |

### Section 02 — Convergence Diagnostics

**Verdict Banner (top of section):**
- **Pass** (green): R-hat < 1.01, ESS > 400, 0 divergences
- **Conditional Pass** (amber): R-hat/ESS thresholds met, divergences > 0
- **Fail** (red): Any threshold breached

**Per-parameter table:**
- Columns: Parameter | R-hat | ESS (Bulk) | ESS (Tail) | Status badge (Pass/Warn/Fail)
- Grouped by: Hierarchical Base Elasticity, Hierarchical Promo Elasticity, Shared Parameters, Sampler Health
- Each parameter has inline description (e.g., "μ_base (global mean base elasticity)")
- Final row: Divergent transitions — "X of Y draws (Z%)" with Review badge

### Section 03 — Model Fit & Predictive Performance

**Status: PLACEHOLDER — Good to have, not must-have**

**Metrics table:**
- Bayesian R², RMSE (in-sample), LOO-IC
- Each with "What it tells you" column
- Flagged as "not yet computed" until `az.r2_score()`, `az.waic()`, `az.loo()` added to pipeline

**Actual vs Predicted trend line plots:**
- 1 panel Overall + 1 per retailer (3 panels)
- Observed weekly volume overlaid with posterior predictive mean
- Requires `pm.sample_posterior_predictive()` — planned enhancement
- Base64 embedded when implemented

**Rationale callout:**
- Explains why good-to-have: convergence proves sampler worked, model fit proves the model itself is useful
- Critical for: (a) comparing model versions, (b) production deployment, (c) stakeholder trust
- Does NOT block business decisions from current elasticity estimates

### Section 04 — Coefficient Estimates (Overall + By Retailer)

**4a. Base Price Elasticity Table:**
- Columns: Retailer | Mean | SD | 95% HDI | P(direction) | P(elastic: |ε|>1) | 1% Price Increase → impact
- Rows: Overall/μ_base (bold/shaded) → BJ's → Costco → Sam's Club
- HDI = Highest Density Interval via `az.hdi()`
- Callout with insight (auto-generated: ranks retailers by sensitivity)

**4b. Promotional Elasticity Table:**
- Same structure as 4a
- Additional column: |Promo|/|Base| Ratio
- "1pp Deeper Discount →" uses semi-elasticity: (e^(β × −0.01) − 1) × 100
- Callout with insight (auto-generated: ranks by promo responsiveness)

**4c. Shared Parameters Table:**
- Cross-price, Spring, Summer, Fall, Time Trend, σ (noise)
- Each with "Business Impact" column translating to plain English
- HDI-crosses-zero check auto-flagged for cross-price and fall ("not reliable")

**4d. Hierarchical Spread Table:**
- σ_base and σ_promo with Mean, 95% HDI
- Auto-generated interpretation: low (<0.15) / moderate (0.15–0.5) / high (>0.5) heterogeneity

**4e. Data Availability Table:**
- Columns: Retailer | Source | Obs | has_promo | has_competitor | Notes

### Section 05 — Coefficient Explorer (Interactive)

**Three calculators, each with Overall + 3 retailers in output:**

| Calculator | Slider Range | Output Columns | Special Treatment |
|---|---|---|---|
| Base Price | −5% to +5%, step 0.5% | Retailer, Elasticity, Volume Impact, Revenue Impact | Standard |
| Promo Discount | 1% to 25% off, step 1% | Retailer, β_promo, Volume Impact, Revenue Impact | Standard |
| Cross-Price | −5% to +5%, step 0.5% | Retailer, β_cross, SI Volume Impact (Mean), SI Volume Impact (HDI Range) | **Amber border + warning banner** ("95% HDI includes zero — directional only"). Costco grayed out as N/A. No revenue column. |

**Formulas displayed below each calculator in monospace.**

### Appendix A1 — Prior Distributions
- Table: Parameter | Prior | Rationale
- All priors with business justification
- Values confirmed from `bayesian_models.py` at generation time
- Warning note if priors are placeholder/representative

### Appendix A2 — MCMC Trace Plots
- All parameters
- Left panel = posterior density per chain, Right panel = sampled values time series
- Base64 embedded PNG

### Appendix A3 — Posterior Distributions
- All parameters
- Histograms with mean (red dashed) and 95% HDI bounds (green dotted) overlaid
- Base64 embedded PNG

---

## 3. BUSINESS DECISION BRIEF

**Audience:** Commercial leadership  
**Purpose:** Pricing & promotion decisions  
**Theme:** Dark mode (DM Sans / JetBrains Mono)  
**Narrative approach:** Template-friendly only (short conditional sentences). Designed to be downloaded and optionally fed into LLM for enhanced narrative + custom PDF.

### Headline Cards (4 Rows × 3 Cards)

| Row | Card 1: Price Sensitivity | Card 2: Promo Power | Card 3: Demand Trend |
|---|---|---|---|
| **Overall** (larger cards, GLOBAL ESTIMATE tag) | Overall base elasticity + confidence pill + 1-line template | |Promo|/|Base| ratio + confidence pill + 1-line template | Annualized β_time + confidence pill + 1-line template |
| **BJ's** (CIRCANA tag) | Retailer elasticity + pill + relative label (auto: "Least/Most sensitive") | Retailer ratio + pill + relative label | −4.6% + **SHARED** pill + "shared estimate" note |
| **Costco** (CRX tag) | Same pattern | Same pattern | Same SHARED pattern |
| **Sam's Club** (CIRCANA tag) | Same pattern | Same pattern | Same SHARED pattern |

**Card sizing:** Overall row = 32px value font. Retailer rows = 26px. Colored top border accent per metric.

**Auto-generation logic for relative labels:**
- Sort retailers by |elasticity|
- Least sensitive = min |base_elasticity|
- Most sensitive = max |base_elasticity|
- Middle = "Mid-range"

### Base Price Impact Section

**Overall scenario table:**
- Rows: −5%, −3%, −1%, +1%, +3%, +5%
- Columns: Price Change | Volume Impact | Revenue Impact | Confidence pill

**By-retailer table (1% increase):**
- Overall (shaded row) + 3 retailers
- Columns: Retailer | Base Elasticity | Volume Impact | Revenue Impact | Confidence | Relative Sensitivity label
- Revenue formula: `(1 + vol_impact/100) × (1 + price_change/100) − 1`

**Horizontal bar chart (CSS-only, no images):**
- Auto-sorted by |elasticity|
- Bar width = retailer |elasticity| / max |elasticity| × 80%
- Color: least sensitive = blue, most sensitive = red

### Promotional Impact Section

**Overall scenario table:**
- Rows: 5%, 10%, 15%, 20% off
- Columns: Discount | Volume Impact | Revenue Impact | Revenue per 1pp | Confidence
- Volume formula: `(e^(β_promo × −depth/100) − 1) × 100`
- Revenue per 1pp = Revenue Impact / discount depth (shows diminishing returns)

**By-retailer table (10% discount):**
- Overall + 3 retailers
- Additional column: Promo/Base Ratio

**Horizontal bar chart:**
- Volume impact of 10% discount by retailer
- Green bars, auto-sorted by responsiveness

### Cross-Price Section

- **Amber warning banner:** "95% range includes zero — not statistically distinguishable from no effect"
- Table: Overall + 3 retailers
- Costco marked "masked (no PL data)" with N/A pill
- LOW confidence pills on all active rows

### Seasonality Cards

- 4 cards in a row: Winter (baseline, gray) | Spring (+X%, green) | Summer (+X%, amber, highlighted) | Fall (+X%, purple)
- Values computed: `(e^β − 1) × 100`
- Confidence pills: HIGH for Spring/Summer (if HDI excludes zero), LOW for Fall (if HDI includes zero)
- Note: "Shared across all retailers"

### Demand Trend Alert

- Red alert banner with 🚨 icon
- Shows annualized decline with 95% range
- Notes 3-year cumulative erosion: `(1 + annual_rate)^3 − 1`
- Flagged as shared estimate
- Conditional: if trend is positive, banner becomes green "Demand Growth" alert

### Historical Price Change Evidence Table

**This is a key differentiator — model validation through observed data.**

| Specification | Detail |
|---|---|
| **Threshold** | Show weeks where \|base price week-over-week % change\| > 1% |
| **Detection** | `df.groupby('Retailer')['Base_Price_SI'].pct_change()` |
| **Columns** | Retailer \| Date \| Price Move (%) \| Observed Volume Impact \| Model Predicted Impact \| Match |
| **Observed Impact** | 4-week avg volume AFTER price change vs 4-week avg volume BEFORE. Percentage difference. |
| **Model Predicted** | Retailer-specific `base_elasticity × observed_price_change_%`. Uses that retailer's own elasticity, not overall. |
| **Match: Close** (green) | Observed within ±1.5pp of predicted |
| **Match: Directional** (amber) | Same direction, within ±3pp |
| **Match: Poor** (red) | >3pp difference or wrong direction |
| **Evidence box** | Below table. Monospace. Explains methodology, threshold, and match criteria. |

### Interactive Scenario Planner

**3 sliders:**

| Slider | Range | Step |
|---|---|---|
| Base Price Change | −5% to +5% | 0.5% |
| Promo Discount Depth | 0% to 25% | 1% |
| Promo Weeks per Year | 0 to 16 | 1 |

**Output table:** Retailer | Base Week Rev Impact | Promo Week Rev Impact | Blended Annual Impact | Confidence pill  
**Rows:** Overall (shaded) + BJ's + Costco + Sam's Club

**Calculation logic:**
- Base week volume: `elasticity × price_pct`
- Base week revenue: `(1 + vol/100) × (1 + price/100) − 1`
- Promo week volume: `(e^(β_promo × −discount/100) − 1) × 100 + base_vol_impact`
- Promo week revenue: `(1 + vol/100) × effective_price − 1` where `effective_price = (1 + price/100) × (1 − discount/100)`
- Blended annual: `(base_rev × base_weeks + promo_rev × promo_weeks) / 52`

**Formula displayed below table in monospace.**

### Key Findings Summary Table

- Numbered table: # | Finding (1-line template sentence) | Applies To | Confidence pill
- Code-generated from conditional logic
- This table is the **primary input for LLM-enhanced narrative generation**

**Conditional rules for findings generation:**

| Condition | Finding |
|---|---|
| \|base_elasticity\| > 1 | "Demand is elastic — any base price increase reduces revenue" |
| \|base_elasticity\| ≤ 1 | "Demand is inelastic — modest price increases may grow revenue" |
| promo/base ratio > 1.5 | "Promotions are {ratio}× more effective than base price changes" |
| Revenue per 1pp decreasing | "Moderate discounts ({optimal}%) more efficient than deep discounts" |
| peak_season_impact > 10% | "{Peak season} promotions generate ~{X}% more absolute volume than winter" |
| annual_trend < −2% | "Underlying demand declining {X}% annually" |
| annual_trend > +2% | "Underlying demand growing {X}% annually" |
| cross_price HDI excludes zero | "Private Label pricing has meaningful impact on SI volume" |
| cross_price HDI includes zero | "Private Label pricing has negligible impact on SI volume" |
| retailer elasticities differ | "{Least} is least price-sensitive; {Most} is most price-sensitive" |
| max promo/base ratio > 2.0 | "{Retailer} has highest promo-to-base ratio ({X}×) — best Hi-Lo candidate" |

---

## 4. CODE STRUCTURE

```
visualizations.py
├── _embed_image(path) → str
│   Converts PNG to base64-embedded <img> tag
│
├── generate_statistical_report(results, data, output_dir)
│   ├── _compute_stat_findings(results, data) → dict
│   ├── _generate_stat_plots(results, data, output_dir) → dict of paths
│   ├── _render_stat_html(findings, plot_paths) → str
│   └── Writes: {output_dir}/statistical_validation_report.html
│
├── generate_business_report(results, data, output_dir)
│   ├── _compute_business_findings(results, data) → dict
│   ├── _compute_historical_evidence(data, findings) → list of dicts
│   │   Detection: pct_change > 1% threshold
│   │   Observed: 4-week avg after vs before
│   │   Predicted: retailer elasticity × price change
│   │   Match classification: close/directional/poor
│   ├── _generate_conditional_labels(findings) → dict
│   │   Retailer rankings, confidence pills, relative labels
│   ├── _render_business_html(findings, evidence, labels) → str
│   └── Writes: {output_dir}/business_decision_brief.html
│
└── generate_html_report(results, data, output_dir)  [LEGACY - calls both above]
```

**run_analysis.py changes:**
```python
# Step 5: Generate reports (gated by config)
if config.get('generate_statistical_report', True):
    generate_statistical_report(results, prepared_data, output_dir)
if config.get('generate_business_report', True):
    generate_business_report(results, prepared_data, output_dir)
```

---

## 5. WHAT THE CODE GENERATES vs WHAT THE LLM ENHANCES

| Element | Code Generates | LLM Enhances (Optional Downstream) |
|---|---|---|
| Headline cards | Numbers, pills, 1-line template labels | — |
| Scenario tables | All numbers, revenue/volume calculations | — |
| Bar charts | CSS bars, auto-sorted, auto-labeled | — |
| Seasonal cards | Computed values, pills | — |
| Historical evidence | Full table from data scan | — |
| Interactive simulator | Full JS with sliders + formulas | — |
| Key findings table | Conditional 1-line sentences | Expand into multi-paragraph recommendations |
| Insight narratives | Short template sentences only | Full strategic analysis with tradeoffs |
| Summary recommendations | NOT generated (just findings table) | Full ranked recommendations with rationale |
| EDLP vs Hi-Lo analysis | Numbers in simulator | Full strategic comparison |
| Root cause discussion | "Trend is declining X%" | Hypotheses, next steps, investigation plan |

---

## 6. MOCKUP REFERENCES

| Report | Mockup File | Status |
|---|---|---|
| Statistical Validation Report | `statistical_report_v2.html` | Agreed ✓ |
| Business Decision Brief | `business_report_v2.html` | Agreed ✓ |

Both mockups use placeholder/representative numbers. Production code will populate from actual model outputs.

---

## 7. SIGN-OFF

- [ ] Statistical Report structure approved
- [ ] Business Report structure approved
- [ ] Base64 embedding requirement confirmed
- [ ] 1 decimal place formatting confirmed
- [ ] "Impact" terminology confirmed
- [ ] Overall + By Retailer everywhere confirmed
- [ ] Confidence pill thresholds confirmed
- [ ] Historical evidence table (1% threshold) confirmed
- [ ] Interactive scenario planner confirmed
- [ ] Template-friendly narratives only (LLM enhancement downstream) confirmed
- [ ] Code architecture approved

**Ready for production code.**
