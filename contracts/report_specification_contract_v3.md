# REPORT SPECIFICATION CONTRACT — V3 AMENDMENT
## Bayesian Price Elasticity Analysis — Sparkling Ice (Club Channel)

**Version:** 2.1 (amends v2.0)  
**Date:** February 7, 2026  
**Prepared by:** Atul (Data Science) + Claude (AI Assistant)  
**Status:** AGREED — Ready for Production Code  
**Supersedes:** `report_specification_contract.md` v1.0, v2.0 (Feb 7, 2026)  
**Mockup files:** `business_report_v3.html`, `statistical_report_v3.html`

---

## 0. PURPOSE OF THIS DOCUMENT

This contract documents **everything that changed between the v2 and v3 mockups**, the **dynamic number injection requirements** for production code, and all **constraints that carry forward unchanged** from v1.0. It is the single source of truth for anyone writing the production `visualizations.py` code.

---

## 1. WHAT CHANGED FROM V2 TO V3

### 1.1 Summary of Changes

| # | Change | Affects | Business Rationale |
|---|---|---|---|
| 1 | Season-aware promo week allocation (4 sliders replace 1) | Both reports | Same % promo lift generates different absolute revenue by season; leadership needs to see this |
| 2 | Volume lift + Revenue lift shown separately | Both reports | Volume ≠ revenue; previous version only showed revenue, hiding the mechanism |
| 3 | Demand erosion projection (Year 1–3) | Both reports | Strategy impact alone is misleading without accounting for −4.6% annual baseline decline |
| 4 | Formula transparency expanded | Both reports | Derivation box now explains seasonal multipliers, erosion math, and the distinction between strategy vs. erosion |
| 5 | Dark mode theme | Statistical report only | Was light mode (IBM Plex on white); now matches business report's dark palette for visual consistency |
| 6 | Dynamic Key Findings with expandable rationale | Business report | All 8 findings + evidence now generated from coefficients; no hardcoded sentences; click-to-expand rationale |

### 1.2 Change 1 — Season-Aware Promo Week Allocation

**V2 (removed):**
```
[Single slider] Promo Weeks / Year: 0–16 weeks
```

**V3 (replacement):**
```
[4 sliders]
  Winter promo weeks:  0–13  (baseline, multiplier = 1.000)
  Spring promo weeks:  0–13  (multiplier = e^0.090 = 1.094)
  Summer promo weeks:  0–13  (multiplier = e^0.197 = 1.218)
  Fall promo weeks:    0–13  (multiplier = e^0.022 = 1.022)

Total indicator: "Total: X of 52 weeks" with red warning if > 52
```

**Why this matters:** The model's seasonal dummies (β_spring, β_summer, β_fall) are additive in log-space, meaning they act as multiplicative volume shifters. A 10% discount in summer produces the same *percentage* volume lift as in winter, but the *absolute* volume gain is ~22% larger because the seasonal base is higher. The v2 simulator treated all promo weeks identically, hiding this compounding effect.

**Seasonal multiplier source (dynamic):**
```python
# Production code must inject these from results.seasonal_effects
spring_mult = math.exp(results.seasonal_effects['Spring'].mean)
summer_mult = math.exp(results.seasonal_effects['Summer'].mean)
fall_mult   = math.exp(results.seasonal_effects['Fall'].mean)
```

**Each seasonal slider label displays the multiplier value** so the user sees the compounding factor. Business report shows `+9.4%`, `+21.8%`, `+2.2%`. Statistical report shows `e^0.090 = 1.094`, `e^0.197 = 1.218`, `e^0.022 = 1.022`.

### 1.3 Change 2 — Volume Lift + Revenue Lift Separated

**V2 table columns:**
```
Retailer | Base Week Rev Impact | Promo Week Rev Impact | Blended Annual | Confidence
```

**V3 table columns:**
```
Retailer | Base Wk Vol Lift | Base Wk Rev Impact | Promo Wk Vol Lift | Promo Wk Rev Impact | Blended Annual Vol | Blended Annual Rev | Confidence
```

**Why this matters:** Volume lift and revenue lift diverge because:
- Base week: revenue = volume change × price change (both move)
- Promo week: revenue = volume gain × discounted price (volume up, price down)
- The gap is largest for deep discounts where volume lift is large but price erosion partially offsets it

The `Confidence` column is present in the business report only (not in the statistical report, which relies on the HDI tables above).

### 1.4 Change 3 — Demand Erosion Projection (Year 1–3)

**V2:** Not present. Blended annual was shown as a static number with no time dimension.

**V3:** A new panel appears below the main simulator output table:

```
┌─────────────────────────────────────────────────────────────────┐
│  📉 Net Impact After Demand Erosion (−4.6% / year)             │
│                                                                 │
│  Year │ Strategy Impact │ Cumulative Erosion │ Net Revenue │ V  │
│  ─────┼─────────────────┼────────────────────┼─────────────┼────│
│  Yr 1 │     +2.9%       │      −4.6%         │   −1.7%     │ ↓  │
│  Yr 2 │     +2.9%       │      −9.0%         │   −6.1%     │ ↓  │
│  Yr 3 │     +2.9%       │     −13.2%         │  −10.3%     │ ↓  │
└─────────────────────────────────────────────────────────────────┘
```

**Formulas:**
```
annual_erosion = (e^(β_time × 52) − 1) × 100

cumulative_erosion(Year N) = ((1 + annual_erosion / 100)^N − 1) × 100

net_revenue_impact = blended_annual_strategy + cumulative_erosion
```

**Business report verdict pills:**
| Net Revenue | Verdict | Color |
|---|---|---|
| ≥ +1% | GROWING | Green |
| −1% to +1% | FLAT | Amber |
| < −1% | DECLINING | Red |

**Statistical report:** Shows the same table without verdict pills; header displays the raw `β_time` value.

**Dynamic source:**
```python
beta_time = results.beta_time_trend.mean
annual_erosion = (math.exp(beta_time * 52) - 1) * 100
```

**Key design principle:** The "Strategy Impact" column is constant across all three years — it represents the annual effect of the chosen pricing/promo strategy. The "Cumulative Erosion" column compounds year over year. This separation makes it clear: *strategy is what you control; erosion is what's happening regardless; net tells you whether you're outpacing the decline.*

### 1.5 Change 4 — Expanded Formula Transparency

**V2 formula box:** Single-line blended annual formula only.
```
Blended Annual = (Base week impact × N weeks + Promo week impact × M weeks) ÷ 52
```

**V3 formula box (both reports):** Structured into labeled sections:

```
Per-week impacts:
  Volume lift (base week): base_elasticity × price_change_%
  Volume lift (promo week): (e^(β_promo × −discount/100) − 1) × 100 + base_vol_lift
  Revenue impact (any week): (1 + vol_lift/100) × effective_price_factor − 1
  Effective price (base week): 1 + price_change/100
  Effective price (promo week): (1 + price_change/100) × (1 − discount/100)

Seasonal multipliers:
  Season multiplier: e^β_season → Winter = 1.000, Spring = X, Summer = X, Fall = X
  % volume lift is the same in every season (promo is additive in log-space)
  But absolute volume gain is higher in peak seasons (multiplier × larger base)

Blended annual (strategy impact):
  Scenario_index = Σ_season [ non_promo_wks × season_mult × vol_factor × price_factor
                             + promo_wks × season_mult × promo_vol_factor × eff_price ]
  Baseline_index = Σ_season [ 13 × season_mult ]
  Blended % = (Scenario_index / Baseline_index − 1) × 100

Demand erosion projection:
  β_time = X (weekly), capturing organic demand decline
  Annual erosion = (e^(β_time × 52) − 1) × 100
  Cumulative erosion (Year N) = (1 + annual_erosion/100)^N − 1
  Net revenue impact = Strategy blended annual + Cumulative erosion

  Strategy impact is what you control (pricing + promos).
  Erosion is what is happening to baseline demand regardless of your actions.
  Net impact tells you whether your strategy outpaces the decline.

Current allocation: [dynamic display of non-zero seasonal week counts]
```

All seasonal multiplier values and β_time must be injected dynamically from the `results` object.

### 1.6 Change 5 — Statistical Report Dark Mode

**V2:** Light mode — `#fafaf9` background, `#1a1a18` text, green accents via `#2d5a27`.

**V3:** Dark mode — matching business report's palette:

| CSS Variable | V2 (Light) | V3 (Dark) |
|---|---|---|
| `--bg` | `#fafaf9` | `#0f1117` |
| `--surface` | `#ffffff` | `#1a1d27` |
| `--surface-alt` | `#f5f4f1` | `#232733` |
| `--border` | `#e5e2dc` | `#2e3240` |
| `--text-primary` | `#1a1a18` | `#e8e9ed` |
| `--text-secondary` | `#6b6960` | `#9a9caa` |
| `--text-muted` | `#9c9889` | `#6b6e7d` |
| `--accent` / `--pass` | `#2d5a27` / `#166534` | `#34d399` |
| `--warn` | `#b45309` | `#fbbf24` |
| `--danger` | `#b91c1c` | `#f87171` |
| `--blue` | `#1e40af` | `#60a5fa` |
| `--purple` (equation coefficients) | `#7c3aed` | `#a78bfa` |

**New variable added:** `--surface-hover: #2a2e3b` and `--border-light: #3a3f50` (carried over from business report).

**Font family unchanged:** IBM Plex Sans / IBM Plex Mono (loaded via Google Fonts).

**Print stylesheet updated:** Reverses to light backgrounds (`#fff` / `#f5f5f5`) for paper output.

### 1.7 Change 6 — Dynamic Key Findings with Expandable Rationale

**V2:** 8 hardcoded `<tr>` rows in the HTML. Each row had a manually written sentence, a manually assigned "Applies To", and a manually assigned confidence pill. **Changing the model coefficients would leave stale findings in the report.**

**V3:** The entire Key Findings section is generated at runtime by a self-contained JS function `(function() { ... })()` that reads the same `R`, `SEASON`, `BETA_TIME`, and cross-price constants used by the simulator. The `<tbody id="findings-body">` starts empty and is populated on page load.

#### 1.7.1 Interaction Design

- **Default view:** 8 one-liner findings with `#`, `Finding`, `Applies To`, `Confidence` — identical visual layout to v2
- **Click any row:** Expands an evidence/rationale panel directly below that row
- **Click again:** Collapses it
- **CSS:** `.finding-row` (clickable) + `.finding-rationale` (hidden by default, shown via `.open` class)
- **Toggle indicator:** Small `▶` arrow rotates to `▼` when expanded

#### 1.7.2 The 8 Findings — Condition → Title → Rationale

**Finding 1 — Demand Elasticity**

| Property | Dynamic Logic |
|---|---|
| **Condition** | `|base_overall| > 1` → elastic; `≤ 1` → inelastic |
| **Title (elastic)** | "Demand is elastic — any base price increase reduces revenue" |
| **Title (inelastic)** | "Demand is inelastic — moderate price increases may grow revenue" |
| **Color** | `var(--red)` |
| **Applies To** | "All retailers" |
| **Confidence** | elastic → HIGH; inelastic → MODERATE |
| **Rationale** | Overall elasticity value + 95% CI. +3% price scenario showing volume + revenue impact. Per-retailer breakdown with individual +3% revenue impacts. `"{most} is {X}% more price-sensitive than {least}."` where retailers are ranked by `|base_elasticity|`. |

**Finding 2 — Promo Power**

| Property | Dynamic Logic |
|---|---|
| **Condition** | Always shown |
| **Title** | `"Promotions are {ratio}× more effective than base price changes"` where `ratio = |promo_overall| / |base_overall|` |
| **Color** | `var(--green)` |
| **Applies To** | `"All retailers ({max_retailer} highest at {max_ratio}×)"` |
| **Confidence** | HIGH |
| **Rationale** | Overall promo and base elasticity values. 10% discount volume lift. Per-retailer promo/base ratio cards ranked descending. `"{top_retailer} gets {ratio}× return from promo dollars vs. permanent price reductions — strongest Hi-Lo candidate."` |

**Finding 3 — Diminishing Returns**

| Property | Dynamic Logic |
|---|---|
| **Condition** | Always true for exponential (semi-elasticity) models |
| **Title** | "Moderate discounts (10%) more efficient than deep discounts (20%)" |
| **Color** | `var(--green)` |
| **Applies To** | "All retailers" |
| **Confidence** | HIGH |
| **Rationale** | 4 mini-cards showing total revenue impact and revenue-per-1pp at 5%, 10%, 15%, 20% off. All values computed from `promoO` coefficient. `"Revenue per 1pp drops from {X}% at 5% off to {Y}% at 20% off."` Explains the exponential decay mechanism. |

**Revenue per 1pp formula:**
```javascript
function revPer1pp(depth) {
    const d = -depth / 100;
    const volPct = (Math.exp(promoO * d) - 1) * 100;
    const revPct = ((1 + volPct / 100) * (1 - depth / 100) - 1) * 100;
    return revPct / depth;
}
```

**Finding 4 — Seasonal Concentration**

| Property | Dynamic Logic |
|---|---|
| **Condition** | Peak season impact > 10% → HIGH; ≤ 10% → MODERATE |
| **Title** | `"{peak_season} promotions generate ~{peak_pct}% more absolute volume than Winter"` where `peak_season` = season with max β, `peak_pct = (e^β_peak − 1) × 100` |
| **Color** | `var(--amber)` |
| **Applies To** | "All retailers (shared)" |
| **Confidence** | Dynamic (see condition) |
| **Rationale** | 4 seasonal cards (Winter/Spring/Summer/Fall) showing: `(e^β − 1) × 100` as %, the raw beta, and the multiplier. Peak season card highlighted with amber border. `"A 10% discount produces the same {vol_lift}% lift in every season. But because {peak}'s base volume is {pct}% higher, the absolute unit gain is ~{pct}% larger."` |

**Finding 5 — Demand Erosion**

| Property | Dynamic Logic |
|---|---|
| **Condition** | `annual_erosion < −2%` → "declining" (RED); `> +2%` → "growing" (GREEN); else → "stable" |
| **Title** | `"Underlying demand {declining/growing/stable} {annual_erosion}% annually"` |
| **Color** | `var(--red)` if declining, `var(--green)` if growing |
| **Applies To** | "All retailers (shared)" |
| **Confidence** | HIGH |
| **Rationale** | β_time value (5 decimals), annualized %. 3 year-cards showing cumulative erosion (Year 1, 2, 3). `"Without pricing or promotional action to offset, baseline volume erodes {cum_3yr}% over 3 years. Any strategy must generate positive revenue impact exceeding {|annual|}% annually to maintain current revenue levels."` |

**Finding 6 — Cross-Price**

| Property | Dynamic Logic |
|---|---|
| **Condition** | `crossCILow < 0 && crossCIHigh > 0` → HDI includes zero → "negligible"; else → "meaningful" |
| **Title (includes zero)** | "Private Label pricing has negligible impact on SI volume" |
| **Title (excludes zero)** | "Private Label pricing has a meaningful impact on SI volume" |
| **Color** | `var(--green)` |
| **Applies To** | "BJ's, Sam's Club" |
| **Confidence** | includes zero → LOW; excludes zero → HIGH |
| **Rationale** | Cross-price mean + 95% CI. Includes/excludes zero statement with bold emphasis. Practical implication: `"A 5% PL price change would shift SI volume by only ~{X}% on the mean estimate — and the true effect could be anywhere from {low} to {high}."` Costco exclusion note. |

**Dynamic source for cross-price (currently hardcoded in JS, must be injected):**
```python
cross_mean = results.elasticity_cross.mean
cross_ci_low = results.elasticity_cross.ci_lower
cross_ci_high = results.elasticity_cross.ci_upper
```

**Finding 7 — Retailer Sensitivity Ranking**

| Property | Dynamic Logic |
|---|---|
| **Condition** | Always shown |
| **Title** | `"{least_name} is least price-sensitive; {most_name} is most price-sensitive"` where retailers sorted by `|base_elasticity|` |
| **Color** | `var(--blue)` |
| **Applies To** | "Retailer-specific" |
| **Confidence** | HIGH |
| **Rationale** | Horizontal bar chart: 3 retailers sorted by `|base_elasticity|`, each with a proportional-width bar (`absBase / max_absBase × 80%`), labels "Least sensitive" / "Mid-range" / "Most sensitive". `"A 1% price increase at {most} loses {pct_diff}% more volume than the same increase at {least}."` where `pct_diff = (most.absBase / least.absBase − 1) × 100`. |

**Finding 8 — Hi-Lo Candidate**

| Property | Dynamic Logic |
|---|---|
| **Condition** | Always shown |
| **Title** | `"{top_name} has the highest promo-to-base ratio ({ratio}×) — best Hi-Lo candidate"` |
| **Color** | `var(--blue)` |
| **Applies To** | `"{top_name}"` |
| **Confidence** | HIGH |
| **Rationale** | Horizontal bar chart: 3 retailers sorted by promo/base ratio descending, each with a proportional-width bar. Top retailer highlighted in green, others in blue. Raw promo + base coefficients shown. `"At {top}, each promotional dollar works {ratio}× harder than a permanent price reduction. {runner_up} is next at {runner_ratio}×."` |

#### 1.7.3 Rationale Visual Components

The rationale panels use these reusable visual elements:

| Component | Usage | Implementation |
|---|---|---|
| **Section label** | `<span class="r-label">Evidence</span>` | Uppercase, 10px, muted, with bottom margin |
| **Highlighted number** | `<span class="r-num">−1.84</span>` | Mono font, subtle background pill |
| **Retailer chip** | `<span class="r-retailer">BJ's ε = −1.65 → +3% price = −2.6% revenue</span>` | Mono font, border, inline-block |
| **Mini-cards grid** | `display:grid; grid-template-columns:repeat(N,1fr)` | Used in Findings 3, 4, 5 |
| **Horizontal bar chart** | Proportional-width `div` inside a fixed container | Used in Findings 7, 8 |

All visual components inherit the dark mode CSS variables — no hardcoded colors.

#### 1.7.4 CSS Classes Added for Findings

```css
.finding-row         /* clickable table row */
.finding-row:hover   /* hover background highlight */
.finding-row.open    /* expanded state — rotates toggle arrow */
.finding-toggle      /* ▶ arrow indicator, positioned absolutely */
.finding-rationale   /* hidden by default (display:none) */
.finding-rationale.open  /* visible state (display:table-row) */
.r-label             /* section header inside rationale */
.r-num               /* highlighted inline number */
.r-retailer          /* retailer chip with coefficients */
```

#### 1.7.5 What This Replaces

The v1.0 contract (§3, Key Findings) described a Python-side `_generate_conditional_labels(findings)` function that would generate 8 template sentences server-side. **In v3, this logic has moved entirely to client-side JS.** The rationale:

- **All required data is already in JS constants** (`R`, `SEASON`, `BETA_TIME`, cross-price) — no need for Python to duplicate the computation
- **The findings update instantly** if the coefficients change (same model, different run → different numbers → different findings)
- **Zero risk of stale text** — there are no hardcoded sentences in the HTML

**Production code impact:** `visualizations.py` does NOT need `_generate_conditional_labels()`. It only needs to inject the coefficient constants into the JS block (already required for the simulator). The findings JS is self-contained and reads those same constants.

#### 1.7.6 Cross-Price Constants — Special Case

The cross-price coefficients (`crossMean`, `crossCILow`, `crossCIHigh`) are currently hardcoded inside the findings JS function (not in the shared constants block at the top of the script). **In production, these must be injected as top-level JS constants** alongside `R`, `SEASON`, and `BETA_TIME`:

```javascript
// Add to the shared constants block:
const CROSS = {
    mean: {cross_mean:.4f},
    ciLow: {cross_ci_low:.4f},
    ciHigh: {cross_ci_high:.4f}
};
```

Then the findings JS references `CROSS.mean` instead of the local `crossMean` variable.

---

## 2. DYNAMIC NUMBER INJECTION — PRODUCTION CODE REQUIREMENTS

### 2.1 The Problem

The v3 mockup HTML files contain **hardcoded placeholder numbers**. Every number that comes from the model must be replaced by Python string interpolation at generation time in `visualizations.py`.

### 2.2 Complete Map of Hardcoded Values → `results` Object Fields

#### 2.2.1 Retailer Elasticities (JS `R` / `COEFFICIENTS` object)

| Hardcoded Value | Results Object Path | Used In |
|---|---|---|
| `base: -1.836` (Overall) | `results.global_elasticity['base'].mean` | Both reports |
| `base: -1.65` (BJ's) | `results.group_elasticities["BJ's"]['base'].mean` | Both reports |
| `base: -2.10` (Costco) | `results.group_elasticities["Costco"]['base'].mean` | Both reports |
| `base: -1.78` (Sam's Club) | `results.group_elasticities["Sam's Club"]['base'].mean` | Both reports |
| `promo: -4.249` (Overall) | `results.global_elasticity['promo'].mean` | Both reports |
| `promo: -4.45` (BJ's) | `results.group_elasticities["BJ's"]['promo'].mean` | Both reports |
| `promo: -3.85` (Costco) | `results.group_elasticities["Costco"]['promo'].mean` | Both reports |
| `promo: -4.42` (Sam's Club) | `results.group_elasticities["Sam's Club"]['promo'].mean` | Both reports |

**Precision:** Inject with `.4f` for JS constants. Display values in HTML tables use 1 decimal (business) or 3 decimal (statistical).

#### 2.2.2 Seasonal Coefficients (JS `SEASON` / `SEASON_BETA` object)

| Hardcoded Value | Results Object Path | Used In |
|---|---|---|
| `beta: 0.090` (Spring) | `results.seasonal_effects['Spring'].mean` | Both reports |
| `beta: 0.197` (Summer) | `results.seasonal_effects['Summer'].mean` | Both reports |
| `beta: 0.022` (Fall) | `results.seasonal_effects['Fall'].mean` | Both reports |
| Winter | Always `0.000` (reference category) | Both reports |

**Note:** The `multiplier` values (`Math.exp(beta)`) are computed in JS at runtime from the injected beta. Do NOT hardcode the multiplier — only inject the beta.

#### 2.2.3 Time Trend / Demand Erosion

| Hardcoded Value | Results Object Path | Used In |
|---|---|---|
| `BETA_TIME = -0.00090` | `results.beta_time_trend.mean` | Both reports (JS) |
| `−4.6%` (annual erosion) | Computed: `(e^(β_time × 52) − 1) × 100` | Both reports (JS + HTML) |
| `−6.4% to −2.8%` (95% range) | `results.beta_time_trend.ci_lower`, `.ci_upper` → annualized | Business report (trend alert banner) |
| `−13% to −14%` (3-year cumulative) | Computed from annual CI bounds | Business report (trend alert banner) |

**Precision:** Inject `β_time` with `.6f` (6 decimal places). The weekly coefficient is tiny; rounding to fewer decimals compounds into meaningful annualized error.

#### 2.2.4 Cross-Price Elasticity

| Hardcoded Value | Results Object Path | Used In |
|---|---|---|
| `CROSS_ELASTICITY = -0.094` / `CROSS.mean` | `results.elasticity_cross.mean` | Both reports (statistical: standalone calculator; business: findings JS) |
| `CROSS_HDI = [-0.229, 0.040]` / `CROSS.ciLow`, `CROSS.ciHigh` | `results.elasticity_cross.ci_lower`, `.ci_upper` | Both reports |

**Note (v2.1 update):** In v2.0 this was listed as "Statistical Report Only". In v3, the cross-price constants are also consumed by the business report's dynamic Key Findings (Finding #6). Production code must inject `CROSS` into the business report JS constants block as well.

#### 2.2.5 Convergence Diagnostics (Statistical Report Only)

| Hardcoded Value | Results Object Path |
|---|---|
| R-hat per parameter | `az.rhat(results.trace)` per parameter |
| ESS Bulk per parameter | `az.ess(results.trace, method='bulk')` per parameter |
| ESS Tail per parameter | `az.ess(results.trace, method='tail')` per parameter |
| Divergence count | `results.n_divergences` |
| Total draws | `results.trace.posterior.dims['draw'] × results.trace.posterior.dims['chain']` |
| Verdict (Pass/Conditional/Fail) | `results.converged`, `results.rhat_max`, `results.ess_min` |

#### 2.2.6 Coefficient Tables (Statistical Report, Section 04)

Every cell in the coefficient tables (4a, 4b, 4c, 4d) must be injected from the corresponding `results` field:

| Table Cell | Source |
|---|---|
| Mean | `posterior_summary.mean` |
| SD | `posterior_summary.std` |
| 95% HDI | `az.hdi(results.trace, hdi_prob=0.95)` per parameter |
| P(negative) | `(samples < 0).mean()` from flattened posterior |
| P(elastic) | `(abs(samples) > 1).mean()` for base elasticity |
| |Promo|/|Base| Ratio | `abs(promo_samples) / abs(base_samples)` element-wise mean |
| 1% Test column | Computed from mean coefficient using appropriate formula |

#### 2.2.7 Business Report — Static Tables & Cards

Every number in the headline cards, scenario tables, bar charts, and seasonal cards is currently hardcoded. All must be computed from `results`:

| Section | Values to Inject | Source |
|---|---|---|
| Headline cards (12 cards) | Elasticity means, promo/base ratios, annual trend, confidence pills, relative labels | `results.group_elasticities`, `results.beta_time_trend` |
| Base price scenario table (6 rows) | Volume impact, revenue impact per price change | `results.base_price_impact(pct)` or compute from mean |
| By-retailer base table (4 rows) | Per-retailer elasticity, volume, revenue, relative sensitivity | `results.group_elasticities` + ranking logic |
| Promo scenario table (4 rows) | Volume, revenue, revenue per 1pp | `results.promo_impact(discount)` or compute from mean |
| By-retailer promo table (4 rows) | Per-retailer promo elasticity, volume, revenue, ratio | `results.group_elasticities` |
| Cross-price table (4 rows) | Cross elasticity, SI volume impact, confidence | `results.elasticity_cross` |
| Seasonal cards (4 cards) | `(e^β − 1) × 100`, confidence pills | `results.seasonal_effects` |
| Trend alert banner | Annual %, 95% range, 3-year cumulative | `results.beta_time_trend` |
| Historical evidence table | Computed from `data` DataFrame | `data.groupby('Retailer')['Base_Price_SI'].pct_change()` |
| Bar chart widths | `retailer |elasticity| / max |elasticity| × 80%` | `results.group_elasticities` |

**Key Findings (updated in v2.1):** No longer listed here. Findings are now fully JS-generated from the injected constants — see §1.7. No additional Python-side generation needed.

### 2.3 Injection Pattern

**Recommended approach:** Use Python f-strings or `.format()` to inject values into the HTML template string inside `visualizations.py`.

```python
def generate_business_report(results, data, output_dir):
    # Extract all dynamic values
    base_overall = results.global_elasticity['base'].mean
    promo_overall = results.global_elasticity['promo'].mean
    beta_time = results.beta_time_trend.mean
    annual_erosion = (math.exp(beta_time * 52) - 1) * 100
    
    retailers = {}
    for name in ["BJ's", "Costco", "Sam's Club"]:
        retailers[name] = {
            'base': results.group_elasticities[name]['base'].mean,
            'promo': results.group_elasticities[name]['promo'].mean,
        }
    
    seasonal = {}
    for season in ['Spring', 'Summer', 'Fall']:
        seasonal[season] = results.seasonal_effects[season].mean
    
    # Cross-price (NEW in v2.1 — needed for dynamic findings)
    cross_mean = results.elasticity_cross.mean
    cross_ci_low = results.elasticity_cross.ci_lower
    cross_ci_high = results.elasticity_cross.ci_upper
    
    # Inject into JS constants block
    js_block = f"""
    const R = {{
        'Overall':    {{ base: {base_overall:.4f}, promo: {promo_overall:.4f} }},
        "BJ's":       {{ base: {retailers["BJ's"]['base']:.4f}, promo: {retailers["BJ's"]['promo']:.4f} }},
        'Costco':     {{ base: {retailers["Costco"]['base']:.4f}, promo: {retailers["Costco"]['promo']:.4f} }},
        "Sam's Club": {{ base: {retailers["Sam's Club"]['base']:.4f}, promo: {retailers["Sam's Club"]['promo']:.4f} }}
    }};
    const BETA_TIME = {beta_time:.6f};
    const ANNUAL_EROSION_PCT = (Math.exp(BETA_TIME * 52) - 1) * 100;
    const SEASON = {{
        winter: {{ beta: 0.000, multiplier: 1.000, maxWeeks: 13, label: 'Winter' }},
        spring: {{ beta: {seasonal['Spring']:.4f}, multiplier: Math.exp({seasonal['Spring']:.4f}), maxWeeks: 13, label: 'Spring' }},
        summer: {{ beta: {seasonal['Summer']:.4f}, multiplier: Math.exp({seasonal['Summer']:.4f}), maxWeeks: 13, label: 'Summer' }},
        fall:   {{ beta: {seasonal['Fall']:.4f}, multiplier: Math.exp({seasonal['Fall']:.4f}), maxWeeks: 13, label: 'Fall' }}
    }};
    const CROSS = {{
        mean: {cross_mean:.4f},
        ciLow: {cross_ci_low:.4f},
        ciHigh: {cross_ci_high:.4f}
    }};
    """
    
    # Similarly inject into HTML body for static tables, cards, etc.
    # ...
    
    html = TEMPLATE.format(js_block=js_block, ...)
    
    output_path = os.path.join(output_dir, 'business_decision_brief.html')
    with open(output_path, 'w') as f:
        f.write(html)
```

### 2.4 Precision Requirements

| Value Type | JS Injection Precision | HTML Display Precision |
|---|---|---|
| Elasticity coefficients | `.4f` | 1 decimal (business), 2–3 decimal (statistical) |
| β_time (weekly) | `.6f` | 5 decimal in statistical derivation box |
| β_season | `.4f` | 3 decimal in multiplier labels |
| Cross-price mean + CI | `.4f` | 3 decimal in findings rationale |
| Percentages (volume/revenue impact) | Computed in JS at full precision | Displayed at 1 decimal (`v.toFixed(1)`) |
| Seasonal multiplier | Computed in JS via `Math.exp(beta)` | 3 decimal in labels |
| Annual erosion % | Computed in JS from β_time | 1 decimal in display |
| P(direction), P(elastic) | Compute from posterior samples | 0 decimal (shown as "97%") |
| R-hat | `.3f` or `.4f` | 3–4 decimal |
| ESS | Integer | Comma-formatted integer |

### 2.5 Conditional Logic That Must Be Dynamic

Several display elements depend on the *values* of the coefficients, not just the numbers:

| Element | Condition | Example |
|---|---|---|
| Relative sensitivity labels | Sort retailers by `|base_elasticity|` | "Least sensitive" = min, "Most sensitive" = max |
| Promo/base ratio | `|promo_mean| / |base_mean|` per retailer | "2.7×" for BJ's |
| Confidence pills | Probability thresholds (95/80/50) | HIGH / MODERATE / LOW |
| Cross-price amber warning | HDI includes zero check | Show/hide warning banner |
| Fall LOW confidence pill | Fall HDI includes zero check | LOW vs HIGH |
| Demand trend banner color | `annual_erosion < 0` → red, `> 0` → green | Conditional class |
| Erosion projection verdict | Net revenue thresholds (±1%) | GROWING / FLAT / DECLINING |
| Key findings titles | 8 conditional rules (see §1.7.2) | Dynamic sentence generation in JS |
| Key findings rationale | Arithmetic + sorting on coefficients (see §1.7.2) | Dynamic evidence panels in JS |
| Key findings confidence pills | Per-finding conditions (see §1.7.2) | Dynamic in JS |
| Bar chart sort order | Sort by `|elasticity|` ascending | Auto-sorted bar widths |
| Costco cross-price row | `has_competitor = 0` → "N/A — masked" | Grayed-out row |

---

## 3. WHAT REMAINS UNCHANGED FROM V1.0

### 3.1 Self-Contained HTML (CRITICAL)

- All images **base64-embedded inline** — zero external file dependencies
- Pattern: `_embed_image(path)` converts PNG to `<img src="data:image/png;base64,{encoded}">`
- One HTML file = complete report, shareable via email / Teams / Slack / Drive
- No separate CSS, JS, or image files
- Google Fonts loaded via `@import url(...)` — this is the **only external dependency** and degrades gracefully (falls back to system sans-serif/monospace)

### 3.2 Formatting Rules

- **1 decimal place** for all displayed numbers. JS computation uses full precision internally.
- **"Impact" terminology everywhere.** Never "lift", "gain", "loss", "decline" interchangeably. The `+`/`−` sign carries directional meaning.
- **Overall + By Retailer everywhere.** Every metric shown at Overall level first, then BJ's, Costco, Sam's Club. No exceptions.

### 3.3 Confidence Pills (Business Report)

| Probability | Label | Color |
|---|---|---|
| 95–100% | HIGH CONFIDENCE | Green |
| 80–94% | MODERATE | Amber |
| 50–79% | LOW | Red |
| Below 50% | NOT RELIABLE | Gray |
| Shared param | SHARED | Gray |

### 3.4 Code Architecture

- Both reports generated from `visualizations.py`
- Two entry points: `generate_statistical_report(results, data, output_dir)` and `generate_business_report(results, data, output_dir)`
- Both consume the same `results` (BayesianResults/HierarchicalResults) + `data` (DataFrame) objects
- Gated by config flags in `config_template.yaml`
- No changes to `data_prep.py`, `bayesian_models.py`, or `run_analysis.py` (except adding the second report call)

### 3.5 Font Families

| Report | Font | Theme |
|---|---|---|
| Business Decision Brief | DM Sans / JetBrains Mono | Dark mode |
| Statistical Validation Report | IBM Plex Sans / IBM Plex Mono | Dark mode (changed from light in v3) |

### 3.6 Report Sections

**Business report sections:**
- Hero header
- Headline cards (4 rows × 3 cards)
- Base price impact (overall table + by-retailer + bar chart)
- Promotional impact (overall table + by-retailer + bar chart)
- Cross-price impact (amber warning + table)
- Seasonality cards (4 cards)
- Demand trend alert (red/green banner)
- Historical evidence table
- Scenario planner (★ MODIFIED in v3 — see §1.2, §1.3, §1.4)
- Key findings summary table (★ MODIFIED in v3 — see §1.7, now fully JS-generated with expandable rationale)
- Footer

**Statistical report sections:**
- Header with metadata grid
- Section 01: Model equation + term-by-term interpretation grid
- Section 02: Convergence diagnostics (verdict banner + per-parameter table)
- Section 03: Model fit & predictive performance (placeholder)
- Section 04: Coefficient estimates (4a–4e sub-tables + callouts)
- Section 05: Coefficient Explorer (base, promo, cross-price calculators + ★ NEW in v3: blended simulator)
- Appendix A1: Prior distributions table
- Appendix A2: MCMC trace plots (base64 placeholder)
- Appendix A3: Posterior distributions (base64 placeholder)
- Footer

### 3.7 Historical Evidence Table

Unchanged from v1.0. Production code computes from `data` DataFrame:

| Spec | Detail |
|---|---|
| **Threshold** | `|base price week-over-week % change| > 1%` |
| **Detection** | `df.groupby('Retailer')['Base_Price_SI'].pct_change()` |
| **Observed impact** | 4-week avg volume AFTER vs 4-week avg BEFORE, as percentage |
| **Model predicted** | Retailer-specific `base_elasticity × observed_price_change_%` |
| **Close match** (green) | Observed within ±1.5pp of predicted |
| **Directional match** (amber) | Same direction, within ±3pp |
| **Poor match** (red) | >3pp difference or wrong direction |

### 3.8 What Code Generates vs What LLM Enhances

Unchanged from v1.0. The reports are template-friendly — all content is code-generated (now including JS-generated Key Findings). LLM enhancement is an optional downstream step for multi-paragraph executive narratives, but is **not required** — the v3 findings with expandable rationale provide sufficient evidence without LLM intervention.

---

## 4. BLENDED ANNUAL FORMULA — V3 COMPLETE SPECIFICATION

This is the full mathematical specification for the season-aware blended simulator, written to be directly translatable to both JS (client-side) and Python (production `_compute_business_findings()`).

### 4.1 Inputs

| Input | Source | Range |
|---|---|---|
| `pc` | Base price change slider | −5% to +5%, step 0.5% |
| `disc` | Promo discount depth slider | 0% to 25%, step 1% |
| `pw[s]` | Promo weeks per season (4 values) | 0–13 per season, step 1 |
| `β_base[r]` | Retailer base elasticity | From `results` |
| `β_promo[r]` | Retailer promo elasticity | From `results` |
| `β_season[s]` | Seasonal coefficient | From `results` (Winter = 0) |
| `β_time` | Weekly time trend | From `results` |

### 4.2 Per-Week Computations

```
Base week volume lift:
  base_vol_pct = β_base[r] × pc

Base week revenue impact:
  base_rev_pct = (1 + base_vol_pct/100) × (1 + pc/100) − 1

Promo week volume lift (from discount):
  promo_vol_from_disc = (e^(β_promo[r] × −disc/100) − 1) × 100

Promo week total volume lift:
  promo_vol_total = base_vol_pct + promo_vol_from_disc

Effective price during promo:
  eff_price = (1 + pc/100) × (1 − disc/100)

Promo week revenue impact:
  promo_rev_pct = (1 + promo_vol_total/100) × eff_price − 1
```

### 4.3 Season-Weighted Blended Annual

```
For each season s ∈ {Winter, Spring, Summer, Fall}:
  season_mult[s] = e^(β_season[s])
  non_promo_wks[s] = 13 − pw[s]

Scenario volume index:
  Σ_s [ non_promo_wks[s] × season_mult[s] × (1 + base_vol_pct/100)
       + pw[s] × season_mult[s] × (1 + promo_vol_total/100) ]
  (when disc = 0, promo weeks use base_vol_pct instead)

Baseline volume index:
  Σ_s [ 13 × season_mult[s] ]

Blended volume % = (Scenario_vol / Baseline_vol − 1) × 100

Scenario revenue index:
  Σ_s [ non_promo_wks[s] × season_mult[s] × (1 + base_vol_pct/100) × (1 + pc/100)
       + pw[s] × season_mult[s] × (1 + promo_vol_total/100) × eff_price ]

Baseline revenue index:
  Σ_s [ 13 × season_mult[s] × 1.0 ]

Blended revenue % = (Scenario_rev / Baseline_rev − 1) × 100
```

### 4.4 Demand Erosion Projection

```
annual_erosion = (e^(β_time × 52) − 1) × 100

For Year N ∈ {1, 2, 3}:
  cumulative_erosion[N] = ((1 + annual_erosion/100)^N − 1) × 100
  net_revenue[N] = blended_revenue_pct + cumulative_erosion[N]
```

**Note:** The projection uses the Overall retailer's blended revenue as the strategy impact value. This is intentional — the erosion is a shared (non-retailer-specific) parameter, so netting it against the Overall blended gives the most meaningful summary.

---

## 5. COMPLETE JS CONSTANTS BLOCK — PRODUCTION TEMPLATE

This is the definitive list of all JS constants that `visualizations.py` must inject. Both reports consume a subset of these; the business report uses all of them.

```javascript
// ── Retailer elasticities (from posterior means) ──
const R = {
    'Overall':    { base: ${base_overall}, promo: ${promo_overall} },
    "BJ's":       { base: ${bjs_base}, promo: ${bjs_promo} },
    'Costco':     { base: ${costco_base}, promo: ${costco_promo} },
    "Sam's Club": { base: ${sams_base}, promo: ${sams_promo} }
};

// ── Seasonal coefficients (shared across retailers) ──
const SEASON = {
    winter: { beta: 0.000, multiplier: 1.000, maxWeeks: 13, label: 'Winter' },
    spring: { beta: ${beta_spring}, multiplier: Math.exp(${beta_spring}), maxWeeks: 13, label: 'Spring' },
    summer: { beta: ${beta_summer}, multiplier: Math.exp(${beta_summer}), maxWeeks: 13, label: 'Summer' },
    fall:   { beta: ${beta_fall}, multiplier: Math.exp(${beta_fall}), maxWeeks: 13, label: 'Fall' }
};

// ── Demand erosion ──
const BETA_TIME = ${beta_time};
const ANNUAL_EROSION_PCT = (Math.exp(BETA_TIME * 52) - 1) * 100;

// ── Cross-price (business report findings + statistical report calculator) ──
const CROSS = {
    mean: ${cross_mean},
    ciLow: ${cross_ci_low},
    ciHigh: ${cross_ci_high}
};
```

**Statistical report additionally needs** (for the standalone calculators in Section 05):
```javascript
const COEFFICIENTS = {
    base: { /* same as R but keyed differently for legacy calculator */ },
    promo: { /* same */ }
};
const CROSS_ELASTICITY = CROSS.mean;
const CROSS_HDI = [CROSS.ciLow, CROSS.ciHigh];
```

---

## 6. PRODUCTION CODE CHECKLIST

### 6.1 `visualizations.py` Changes Required

- [ ] `generate_business_report()`: Inject all JS constants from §5 via f-string
- [ ] `generate_business_report()`: Replace hardcoded HTML table values with computed values from `results`
- [ ] `generate_business_report()`: Add `_compute_historical_evidence(data, findings)` for evidence table
- [ ] `generate_business_report()`: Key Findings section requires NO Python generation — it is fully JS-driven from the injected constants
- [ ] `generate_statistical_report()`: Inject `COEFFICIENTS`, `SEASON_BETA`, `BETA_TIME`, `CROSS_ELASTICITY`, `CROSS_HDI`
- [ ] `generate_statistical_report()`: Inject convergence diagnostics from ArviZ
- [ ] `generate_statistical_report()`: Inject coefficient tables (4a–4e) from posterior summaries
- [ ] Both: Embed plot PNGs via `_embed_image()` into base64 `<img>` tags
- [ ] Both: Write self-contained HTML to `{output_dir}/business_decision_brief.html` and `{output_dir}/statistical_validation_report.html`

### 6.2 `run_analysis.py` Changes Required

```python
# Step 5: Generate reports (gated by config)
if config.get('generate_statistical_report', True):
    generate_statistical_report(results, prepared_data, output_dir)
if config.get('generate_business_report', True):
    generate_business_report(results, prepared_data, output_dir)
```

### 6.3 `config_template.yaml` — No New Keys Required

The v3 changes are purely presentation-layer. No new config keys are needed. The seasonal betas, time trend, cross-price, and retailer elasticities all flow from the existing `results` object.

---

## 7. MOCKUP FILES

| Report | V2 Mockup | V3 Mockup | Status |
|---|---|---|---|
| Statistical Validation Report | `statistical_report_v2.html` (light) | `statistical_report_v3.html` (dark) | Agreed ✓ |
| Business Decision Brief | `business_report_v2.html` | `business_report_v3.html` | Agreed ✓ |

Both v3 mockups use placeholder/representative numbers. Production code will populate from actual model outputs using the injection patterns documented in §2 and §5.

---

## 8. SIGN-OFF

**Carried forward from v1.0 (confirmed):**
- [x] Base64 embedding requirement
- [x] 1 decimal place formatting
- [x] "Impact" terminology
- [x] Overall + By Retailer everywhere
- [x] Confidence pill thresholds
- [x] Historical evidence table (1% threshold)
- [x] Code architecture (visualizations.py entry points)

**New in v3 (to confirm):**
- [ ] Season-aware promo allocation (4 sliders) approved
- [ ] Volume lift + Revenue lift separation approved
- [ ] Demand erosion projection (Year 1–3) approved
- [ ] Expanded formula transparency approved
- [ ] Statistical report dark mode approved
- [ ] Dynamic Key Findings with expandable rationale approved
- [ ] Finding conditions and rationale templates (§1.7.2) reviewed
- [ ] Cross-price constants promoted to shared JS block (§1.7.6) approved
- [ ] Complete JS constants template (§5) reviewed
- [ ] Dynamic injection map (§2) reviewed and complete
- [ ] Blended annual formula (§4) mathematically verified
- [ ] Erosion projection formula verified

**Ready for production code.**
