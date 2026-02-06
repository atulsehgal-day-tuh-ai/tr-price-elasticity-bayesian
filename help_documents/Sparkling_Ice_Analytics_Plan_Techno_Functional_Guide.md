# Sparkling Ice Analytics Plan — Techno-Functional Guide
## Business + Technical Guide to Our Price Elasticity System

**Prepared for:** Commercial & Pricing Leadership, Analytics, and Technical Stakeholders  
**Date:** February 5, 2026  
**Version:** 2.0  

---

## Executive Summary (what this is and why it matters)

This guide explains **what we are modeling, why we are modeling it this way, and how the system works end-to-end**—from raw weekly Circana exports to decision-grade elasticity outputs.

At a high level, we estimate **how Sparkling Ice demand changes when price changes**, while controlling for the other forces that move sales (promotions, competitor/private label pricing, seasonality, and long-term trends). The key upgrade in this system is **dual elasticities**:

1. **Base Price Elasticity (strategic)** — consumer response to permanent/everyday price changes  
2. **Promotional Elasticity (tactical)** — consumer response to temporary discounts (typically 2–3× stronger)

The output is not just “one number.” Because we use Bayesian inference, we produce **probability statements** such as:

- “There is an 85% probability that a 3% base price increase decreases revenue.”
- “A 10% discount has a 70% probability of increasing units by at least 15%.”

This document is designed to complement the business narrative in:
- `help_documents/Sparkling_Ice_Analytics_Plan_Business_Guide.md`

---

## Table of Contents

1. [The business goal and decisions enabled](#1-the-business-goal-and-decisions-enabled)  
2. [Why Bayesian (vs classical) for this problem](#2-why-bayesian-vs-classical-for-this-problem)  
3. [MCMC in plain English (chains, samples, NUTS) + why compute matters](#3-mcmc-in-plain-english-chains-samples-nuts--why-compute-matters)  
4. [What models we run: pooled vs hierarchical](#4-what-models-we-run-pooled-vs-hierarchical)  
5. [Data inputs: raw columns we use and features we construct](#5-data-inputs-raw-columns-we-use-and-features-we-construct)  
6. [Dual elasticities: base price vs promotions](#6-dual-elasticities-base-price-vs-promotions)  
7. [Promotion modeling (and why we don’t split feature vs display yet)](#7-promotion-modeling-and-why-we-dont-split-feature-vs-display-yet)  
8. [Brand-level modeling and why UPC-level isn’t required (for now)](#8-brand-level-modeling-and-why-upc-level-isnt-required-for-now)  
9. [Seasonality, holidays, and portfolio changes](#9-seasonality-holidays-and-portfolio-changes)  
10. [“Closer to real” elasticity: isolating the pure price effect](#10-closer-to-real-elasticity-isolating-the-pure-price-effect)  
11. [Outputs: what the system produces and how to interpret them](#11-outputs-what-the-system-produces-and-how-to-interpret-them)  
12. [Implementation pointers: where this is in the repo](#12-implementation-pointers-where-this-is-in-the-repo)  

---

## 1) The business goal and decisions enabled

We want to answer questions like:

- **Strategic pricing (base price elasticity)**  
  - “If we raise base price by 3–5%, what is the probability revenue increases vs decreases?”  
  - “How much pricing power do we have by retailer?”

- **Tactical promotions (promo elasticity)**  
  - “What discount depth maximizes volume vs revenue?”  
  - “Are we more promo-responsive at BJ’s vs Sam’s?”

- **Competitive positioning (cross-price vs private label)**  
  - “If private label price drops, how much share/volume do we lose?”

The system is built for **risk-managed decision-making**: decisions are framed in terms of **probabilities and uncertainty**, not just point estimates.

---

## 2) Why Bayesian (vs classical) for this problem

### Simple analogy: photo vs video

- **Classical statistics** is like taking **one photo** of a moving object: you get one best estimate (plus a confidence interval that is often misinterpreted).  
- **Bayesian statistics** is like making a **short video**: you get a full range of plausible values and can directly ask “how likely is X?”

Example difference in outputs:

- Classical: “Elasticity is -2.0, 95% CI [-2.6, -1.4].”  
- Bayesian: “There’s an **87% probability** elasticity is below -1.8.”

### Why Bayesian fits *our* data

Weekly retail data is **noisy** and influenced by overlapping drivers:

- Base prices move slowly (strategic decisions)
- Promotions cause short spikes (tactical actions)
- Competitor/private label pricing shifts the market basket
- Seasonality and time trends change baseline demand

Bayesian modeling is a strong fit because it:

- Produces **full uncertainty distributions** for every parameter
- Supports **hierarchical pooling** across retailers
- Enables **direct probability statements** for decision-making

---

## 3) MCMC in plain English (chains, samples, NUTS) + why compute matters

Bayesian models typically don’t have a simple closed-form solution. We approximate the posterior distribution using **Markov Chain Monte Carlo (MCMC)**.

- **Posterior distribution**: the “video” of plausible parameter values after seeing our data  
- **A chain**: one independent “explorer” walking around the space of plausible values  
- **Sampling within a chain**: each step is one plausible set of parameters (elasticities, seasonal effects, noise, etc.)  
- **Why multiple chains**: independent explorers should converge to the same region if results are stable  
- **Tuning / warm-up**: early steps help the sampler find stable movement; these are not counted as final evidence

We use **NUTS (No-U-Turn Sampler)**, which is a more efficient MCMC method than simple random-walk MCMC for continuous parameter spaces.

### Why better parallel compute matters

MCMC is compute-intensive because:
- We run **multiple chains** (each chain is effectively a full model fit)
- We draw **thousands of samples** per chain
- Hierarchical + dual-elasticity models have more parameters

The good news: chains are naturally parallelizable. More CPU cores allow:
- Running chains simultaneously (faster turnaround)
- Faster “what-if” scenarios and sensitivity analysis
- More robust diagnostics without long waits

---

## 4) What models we run: pooled vs hierarchical

We fit one of two Bayesian demand models on weekly data:

### Model A — Simple (pooled) Bayesian model
Use when you want one overall elasticity across retailers (or are analyzing a single retailer).

### Model B — Hierarchical Bayesian model (partial pooling)
Use when multiple retailers differ (BJ’s vs Sam’s), but we still want stable estimates even when one retailer has fewer informative weeks.

Both models are **log-demand** models so elasticities are directly interpretable (percent change vs percent change).

---

## 5) Data inputs: raw columns we use and features we construct

This section is the “contract” between the Circana export and the model.

### 5.1 Raw Circana columns actually used (minimum set)

From each retailer CSV, the pipeline uses:

- `Product` (to identify Sparkling Ice vs Private Label aggregates)
- `Time` (weekly date field)
- `Dollar Sales`
- `Unit Sales`
- `Volume Sales` (dependent variable; if missing for a retailer, computed as `Unit Sales × factor` per config)

These are enough to compute:
- Sparkling Ice volume (model outcome)  
- Sparkling Ice average paid price  
- Private Label average price (cross-price feature)

If a retailer file is missing `Volume Sales`, provide a constant factor in configuration (per retailer). Example:

- `volume_sales_factor_by_retailer: { Costco: 2.0 }`

### 5.2 Recommended raw columns for dual elasticities

If present, we also use:

- `Base Dollar Sales`
- `Base Unit Sales`

These allow a **base/regular price** calculation that supports the strategic base-price elasticity.

### 5.3 Optional raw columns used for a promo-intensity proxy (fallback)

If present, we combine these into a single `Promo_Intensity` signal:

- `Unit Sales Any Merch`
- `Unit Sales Feature Only`
- `Unit Sales Display Only`
- `Unit Sales Feature and Display`

If these columns are absent, the pipeline sets promo intensity to 0 and relies on **promo depth** (preferred) when available.

### 5.4 Engineered features the model consumes

From the raw columns, the pipeline builds the features used in the regression:

- **Outcome**
  - `Log_Volume_Sales_SI` (from Sparkling Ice `Volume Sales`; if missing for a retailer, computed as `Unit Sales × factor` per config)

- **Own/base price**
  - `Log_Base_Price_SI` (preferred for dual-elasticity mode)  
  - `Log_Price_SI` (fallback if base price not available)

- **Promotion**
  - `Promo_Depth_SI = (AvgPrice / BasePrice) - 1` (preferred; negative when discounted)  
  - `Promo_Intensity_SI` (fallback proxy)

- **Competitor / private label**
  - `Log_Price_PL`

- **Seasonality**
  - `Spring`, `Summer`, `Fall` (winter is implicit baseline)

- **Trend**
  - `Week_Number` (weeks since first observation)

- **Availability flags** (used to safely include/exclude terms for retailers with missing fields)
  - `has_promo`, `has_competitor`

---

## 6) Dual elasticities: base price vs promotions

### The problem with a single elasticity

A single elasticity number mixes two different consumer behaviors:

- response to **permanent** everyday price changes (strategic)
- response to **temporary** discounts (tactical; urgency/visibility/stock-up)

Using one blended elasticity often:
- overstates the damage of base price increases
- understates promotional ROI

### Our dual-elasticity approach

We separate:

- **Base Price Elasticity**: coefficient on `Log(Base_Price)`  
- **Promotional Elasticity**: coefficient on `Promo_Depth`

Base price and promo depth are computed directly from the “total vs base” sales fields:

- Base Price = `Base Dollar Sales / Base Unit Sales`  
- Average Paid Price = `Dollar Sales / Unit Sales`  
- Promo Depth = `(AvgPrice / BasePrice) - 1`

This is both **interpretable** and **identifiable** with weekly variation.

---

## 7) Promotion modeling (and why we don’t split feature vs display yet)

Circana may provide separate merchandising breakdowns (feature only, display only, feature+display). While valuable, we intentionally start with a single promotion measure:

- **Promo depth** (preferred): captures the *effective discount* regardless of whether it was supported by merchandising
- **Promo intensity** (fallback): uses “Any Merch / Feature / Display” unit columns when present

Why not split feature vs display in the core model yet:
- Those signals are often **correlated** (multicollinearity)
- Many promo types are **sparse**
- More parameters increases compute and uncertainty

Upgrade path: if needed, add explicit feature/display variables later for trade-spend allocation questions.

---

## 8) Brand-level modeling and why UPC-level isn’t required (for now)

We model **brand-level demand** (Sparkling Ice total) rather than every UPC. This is appropriate when decisions are brand-level:
- base price strategy
- promo depth planning
- retailer comparisons
- competitive positioning

Why it’s statistically acceptable:
- Elasticity is identified from **week-to-week variation** in price and promotions.
- UPC mix shifts mostly change the **baseline level**; promotions (which often drive mix shifts) are already modeled.
- UPC-level modeling would create a parameter explosion and add noise unless there is a clear business need.

If future decisions require SKU optimization, we can extend to a UPC hierarchy.

---

## 9) Seasonality, holidays, and portfolio changes

### 9.1 Seasonality controls (explicit)

We include seasonal dummies derived from month:
- Spring (Mar–May)
- Summer (Jun–Aug)
- Fall (Sep–Nov)
Winter is the baseline.

This prevents the model from confusing “summer peak demand” with “price insensitivity.”

### 9.2 Holidays (current baseline + recommended enhancement)

**Current baseline:** no explicit holiday flags in the core pipeline. Holiday effects are partially absorbed by:
- promotions (holiday weeks often coincide with discounting)
- seasonality and time trend
- residual error term

**Recommended enhancement:** add a small set of holiday indicators (e.g., Thanksgiving, Christmas/New Year, July 4 week) if holiday-specific precision is important.

### 9.3 Portfolio changes: why the elasticity remains reliable

A common concern is that new products launching/discontinuing could bias elasticity. We address this in three ways:

1. **Brand-level data** naturally includes the whole portfolio; changes are captured in the aggregate.
2. **Strong seasonal patterns dominate** the largest demand swings, and we control them explicitly.
3. **No evidence of major disruptions** was detected in the observed period; changes were gradual.

Illustrative seasonality signal observed in the weekly series:

| Month | Relative pattern | Interpretation |
|---|---|---|
| March | trough | winter / cold weather |
| Late May | peak | Memorial Day / early summer |
| Mid-December | peak then drop | holiday spike then post-holiday normalization |

---

## 10) “Closer to real” elasticity: isolating the pure price effect

Naïve elasticity (price vs sales correlation) is biased because price changes coincide with other drivers. We explicitly control for major confounders:

- **Promo depth / intensity**: separates discount effects from base pricing
- **Private label price**: controls competitive pressure
- **Seasonality**: removes predictable calendar swings
- **Time trend**: captures gradual changes (distribution, awareness, macro effects)

This does not make the estimate perfectly causal, but it makes it **far closer to true consumer price response** than a simple regression that ignores these factors.

---

## 11) Outputs: what the system produces and how to interpret them

Typical outputs include:

- **Elasticity estimates** (base, promo, cross-price) with credible intervals
- **Retailer-level elasticities** (in hierarchical mode)
- **Probability statements** (e.g., \(P(\\Delta Revenue < 0 \\mid \\Delta Price=+5\\%)\))
- **Diagnostics** (trace plots, R-hat, effective sample size)
- **Standalone HTML reports** (for sharing)

Interpretation notes:
- Elasticities come from log-log coefficients (percent change interpretation).
- When in dual-elasticity mode, use base elasticity for strategic price moves and promo elasticity for discount planning.

---

## 12) Implementation pointers: where this is in the repo

If you want the code-level view, start here:

- `data_prep.py`: raw CSV → model-ready table (prices, base price, promo depth, seasonality, trend)
- `bayesian_models.py`: pooled + hierarchical PyMC models; dual-elasticity selection logic
- `visualizations.py`: plots + HTML report generation
- `run_analysis.py`: CLI orchestration
- `architecture.md`: call graphs, data contracts, and end-to-end flow

### Operational scripts

- Create a Python 3.12 environment:
  - `scripts/setup_venv_py312_windows.ps1`
  - `scripts/setup_venv_py312_linux.sh`

- Export a `help_documents/*.md` file to HTML:
  - Windows: `scripts/convert_help_md_to_html.ps1`
  - Linux/macOS: `scripts/convert_help_md_to_html.sh`

The HTML output goes to the `html/` folder (gitignored by default).

---

## Appendix A — Reference model form (conceptual)

The core model is a log-demand regression with controls:

\[
Log\_Volume\_Sales\_{SI,t} = \\alpha
+ \\beta_{base} \\cdot Log\_Base\_Price\_{SI,t}
+ \\beta_{promo} \\cdot (Promo\_Depth\_{SI,t} \\cdot has\\_promo_t)
+ \\beta_{cross} \\cdot (Log\_Price\_{PL,t} \\cdot has\\_competitor_t)
+ \\beta_{spring} \\cdot Spring_t
+ \\beta_{summer} \\cdot Summer_t
+ \\beta_{fall} \\cdot Fall_t
+ \\beta_{time} \\cdot Week\_Number_t
+ \\epsilon_t
\]

with \(\epsilon_t \sim \mathcal{N}(0, \sigma)\).

### Variable definitions (with source / calculation)

**`Log_Volume_Sales_SI` (dependent variable)**  
- **Raw source**: Circana `Volume Sales` for Sparkling Ice (after filtering `Product` to the Sparkling Ice aggregate)
- **Fallback (strict rule)**: if `Volume Sales` is missing for a retailer, compute `Volume Sales = Unit Sales × factor` using `PrepConfig.volume_sales_factor_by_retailer`
- **Pivoted column**: `Volume_Sales_SI`
- **Transform**: `Log_Volume_Sales_SI = ln(Volume_Sales_SI)` (requires `Volume_Sales_SI > 0`)

**`Log_Base_Price_SI` (strategic/base price)**  
- **Raw source**: `Base Dollar Sales`, `Base Unit Sales` (Sparkling Ice)
- **Derived**: `Base_Price_SI = Base_Dollar_Sales_SI / Base_Unit_Sales_SI` (guard divide-by-zero)
- **Imputation**: if base sales are missing/undefined for some weeks, the pipeline imputes a proxy base price from observed average prices (rolling-window proxy + forward/back-fill; warns if heavy imputation is required)
- **Transform**: `Log_Base_Price_SI = ln(Base_Price_SI)` (requires `Base_Price_SI > 0`)

**`Promo_Depth_SI` (tactical discount depth; semi-elasticity)**  
- **Raw source**: `Dollar Sales`, `Unit Sales` (Sparkling Ice) + base sales columns above
- **Avg price**: `Avg_Price_SI = Dollar_Sales_SI / Unit_Sales_SI`
- **Promo depth**: `Promo_Depth_SI = (Avg_Price_SI / Base_Price_SI) - 1` (negative when discounted)
- **Stability**: NaN/inf handled; values clipped to a conservative range for robustness

**`Log_Price_PL` (private label price / cross-price control)**  
- **Raw source**: `Dollar Sales`, `Unit Sales` for Private Label aggregate (`Product` filter to PL)
- **Derived**: `Price_PL = Dollar_Sales_PL / Unit_Sales_PL`, then `Log_Price_PL = ln(Price_PL)`

**`Spring`, `Summer`, `Fall` (seasonality dummies)**  
- **Derived**: from `Date` month buckets (winter is implicit baseline)

**`Week_Number` (time trend)**  
- **Derived**: `Week_Number = int((Date - min(Date)).days / 7)`

**`has_promo`, `has_competitor` (availability masks)**  
- **Source**: retailer availability config (`PrepConfig.retailers`) and/or inferred availability
- **Usage in equation**: promo and cross-price terms are multiplied by these masks so that missing features contribute 0, preventing bias

**Important:** `Unit Sales` is **not** the dependent variable. It is used for unit-consistent price denominators:
- `Avg_Price_SI = Dollar_Sales_SI / Unit_Sales_SI`
- `Base_Price_SI = Base_Dollar_Sales_SI / Base_Unit_Sales_SI`

In hierarchical mode, the intercept and/or elasticities can vary by retailer with partial pooling.

