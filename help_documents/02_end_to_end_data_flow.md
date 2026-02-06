# End-to-End Data Flow: Raw CSV → Bayesian Model → Business Outputs

**Prepared for:** Atul Sehgal
**Date:** February 6, 2026
**Scope:** Complete field-level traceability across all five codebase files

---

## How to Read This Document

This document traces every column from its origin in a raw CSV file, through each transformation step, into the model's linear predictor, through posterior sampling, and finally into the business outputs (revenue scenarios, plots, HTML report). It also catalogues what is **never used**.

The pipeline has five files executed in this order:

```
config_template.yaml          ← declares all rules
        │
        ▼
run_analysis.py               ← orchestrator (CLI + YAML → pipeline)
        │
        ├──► data_prep.py     ← raw CSVs → model-ready DataFrame
        │
        ├──► bayesian_models.py ← DataFrame → MCMC → posterior samples
        │
        └──► visualizations.py  ← posterior samples + DataFrame → plots + HTML
```

---

## PART 1: SOURCE FILES → RAW COLUMNS

### 1.1 BJ's / Sam's Club (Circana) — 74 columns each

```
File load:  pd.read_csv('bjs.csv', skiprows=2)
            pd.read_csv('sams.csv', skiprows=2)
```

| Raw Column | Used? | Where Consumed |
|---|---|---|
| `Product` | ✅ | `data_prep._clean_data()` — row filtering (SI vs PL) |
| `Time` | ✅ | `data_prep._parse_date_for_retailer()` → `Date` |
| `Dollar Sales` | ✅ | `data_prep._compute_avg_price_for_retailer()` → numerator of `Price_SI` / `Price_PL` |
| `Unit Sales` | ✅ | Denominator of `Price_SI` / `Price_PL`; denominator for `Promo_Intensity` |
| `Volume Sales` | ✅ | Direct → `Volume_Sales_SI` / `Volume_Sales_PL` |
| `Base Dollar Sales` | ✅ | `data_prep._compute_base_price_for_retailer()` → numerator of `Base_Price_SI` |
| `Base Unit Sales` | ✅ | Denominator of `Base_Price_SI` |
| `Unit Sales Any Merch` | ✅ | `data_prep._clean_data()` → `Promo_Intensity` numerator |
| `Unit Sales Feature Only` | ✅ | Same |
| `Unit Sales Display Only` | ✅ | Same |
| `Unit Sales Feature and Display` | ✅ | Same |
| *66 other columns* | ❌ | **UNUSED** (Year Ago comparisons, ACV distribution, store counts, etc.) |

**Total used: 11 of 74 columns (BJ's); same 11 for Sam's**

### 1.2 Costco (CRX) — 28 columns (current `costco.csv` schema)

```
File load:  pd.read_csv('costco.csv', skiprows=1)
```

| Raw Column | Used? | Where Consumed |
|---|---|---|
| `Item` | ✅ | `data_prep._clean_data()` — row filtering (renamed to `Product`) |
| `Time` | ✅ | `data_prep._parse_date_for_retailer()` → regex extract → `Date` |
| `Unit Sales` | ✅ | `Volume Sales` = `Unit Sales × 2.0` (via `volume_sales_factor_by_retailer`) |
| `Dollar Sales` | ✅ | `data_prep._clean_data()` dropna guard (not used for price) |
| `Avg Net Price` | ✅ | Direct → `Price_SI` (**NOT** `Dollar Sales / Unit Sales`) |
| `Non Promoted Dollars` | ✅ | `data_prep._compute_base_price_for_retailer()` → numerator of `Base_Price_SI` |
| `Non Promoted Units` | ✅ | Denominator of `Base_Price_SI` |
| `Average Price per Unit` | ⚠️ | Fallback for `Base_Price_SI` when `Non Promoted Units < 500` (rare; triggered in a small number of weeks in the current extract) |
| `Gross Dollars` | ⚠️ | Validation only (`_validate_costco_data_integrity`) |
| `Gross Units` | ⚠️ | Validation only |
| `Refund Dollars` | ⚠️ | Validation only |
| `Refund Units` | ⚠️ | Validation only |
| `Coupon Dollars` | ⚠️ | Validation only |
| `Coupon Units` | ⚠️ | Validation only |
| `Total Discount Dollars` | ⚠️ | Validation only |
| `Promoted Units` | ⚠️ | Validation only |
| `Avg Net Price` (in validation) | ⚠️ | Cross-check only |
| *Remaining columns* | ❌ | **UNUSED**: `Venue`, `Warehouses Selling`, `Average Dollar Sales per Warehouse Selling`, `Average Unit Sales per Warehouse Selling`, `Item Description`, `Item Number`, `Average Coupon Value`, `Average Promoted Price`, `% Discount`, `Net Dollars`, `Promoted Dollars`, `OOS %` |

**Summary:** Costco model path uses 7 required columns (+ optional `Average Price per Unit` fallback), and Costco v2 adds 6 columns used for validation-only. All other raw columns are unused by the model.

---

## PART 2: TRANSFORMATION PIPELINE (data_prep.py)

Each step below shows what goes in, what comes out, and which function performs it.

```
┌─────────────────────────────────────────────────────────────────┐
│  STEP 1: LOAD + LABEL                                          │
│  _load_single_retailer() per retailer                          │
│                                                                 │
│  Input:  3 raw CSVs                                            │
│  Output: Single stacked DataFrame with 'Retailer' column       │
│          BJ's rows labeled "BJ's"                              │
│          Sam's rows labeled "Sam's Club"                        │
│          Costco rows labeled "Costco"                           │
│          Costco "Item" column renamed → "Product"               │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 2: FILTER PRODUCTS                                       │
│  _clean_data() → _assign_product_short()                       │
│                                                                 │
│  Fuzzy match per retailer using retailer_data_contracts:        │
│    BJ's/Sam's: product contains "sparkling ice" → SI           │
│                product contains "private label" → PL            │
│    Costco:     product contains "sparkling ice core" → SI       │
│                competitor_filter = null → no PL rows            │
│                                                                 │
│  Output column: Product_Short ∈ {'Sparkling Ice','Private Label'}│
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 3: PARSE DATES                                           │
│  _parse_date_for_retailer()                                    │
│                                                                 │
│  BJ's/Sam's: strip "Week Ending " → parse %m-%d-%y             │
│  Costco:     regex "ending (\d{2}-\d{2}-\d{4})" → parse %m-%d-%Y│
│                                                                 │
│  Output column: Date (datetime64)                               │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 4: COMPUTE PRICES (per-retailer)                         │
│  _compute_avg_price_for_retailer()                             │
│  _compute_base_price_for_retailer()                            │
│                                                                 │
│  BJ's/Sam's:                                                   │
│    Avg_Price    = Dollar Sales / Unit Sales                     │
│    Base_Avg_Price = Base Dollar Sales / Base Unit Sales         │
│                                                                 │
│  Costco:                                                        │
│    Avg_Price    = Avg Net Price  (direct column)                │
│    Base_Avg_Price = Non Promoted Dollars / Non Promoted Units   │
│      fallback:    Average Price per Unit (when NP Units < 500)  │
│                                                                 │
│  Output columns: Avg_Price, Base_Avg_Price                      │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 5: COMPUTE VOLUME SALES                                  │
│  _clean_data()                                                  │
│                                                                 │
│  BJ's/Sam's: Volume Sales column exists → direct               │
│  Costco:     Volume Sales = Unit Sales × 2.0                   │
│              (24pk × 17oz = 408oz; 408/204 = 2.0 volume units) │
│                                                                 │
│  Output column: Volume Sales (float)                            │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 6: COMPUTE PROMO INTENSITY                               │
│  _clean_data()                                                  │
│                                                                 │
│  BJ's/Sam's:                                                   │
│    Promo_Intensity = SUM(merch columns) / Unit Sales            │
│    clipped to [0, 1]                                            │
│                                                                 │
│  Costco:                                                        │
│    Promo_Intensity = 0.0  (no merchandising columns in CRX)    │
│                                                                 │
│  Output column: Promo_Intensity (float, per SI row)             │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 7: PIVOT TO WIDE FORMAT                                  │
│  _pivot_to_wide()                                               │
│                                                                 │
│  Grain changes from: Retailer × Product × Week                 │
│                  to:  Retailer × Week                           │
│                                                                 │
│  Pivot creates:                                                 │
│    Volume_Sales_SI  (from SI rows' Volume Sales)                │
│    Volume_Sales_PL  (from PL rows' Volume Sales; NaN at pivot for Costco → masked to 0.0 when has_competitor=0)│
│    Price_SI         (from SI rows' Avg_Price)                   │
│    Price_PL         (from PL rows' Avg_Price; NaN at pivot for Costco → masked to 0.0 when has_competitor=0)   │
│    Base_Price_SI    (from SI rows' Base_Avg_Price)              │
│    Promo_Intensity_SI (from SI rows' Promo_Intensity)           │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 8: TIME FEATURES                                         │
│  _add_time_features()                                           │
│                                                                 │
│  Week_Number = (Date − origin_date).days / 7                   │
│    origin_date = config.week_number_origin_date or min(Date)    │
│                                                                 │
│  Output column: Week_Number (int)                               │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 9: SEASONAL DUMMIES                                      │
│  _add_seasonal_features()                                       │
│                                                                 │
│  Month  = Date.dt.month                                         │
│  Spring = 1 if Month ∈ {3,4,5}, else 0                         │
│  Summer = 1 if Month ∈ {6,7,8}, else 0                         │
│  Fall   = 1 if Month ∈ {9,10,11}, else 0                       │
│  Winter = reference category (all dummies = 0)                  │
│                                                                 │
│  Output columns: Month, Spring, Summer, Fall                    │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 10: BASE PRICE + PROMO DEPTH  (V2)                      │
│  _add_base_and_promo_depth()                                    │
│                                                                 │
│  Base_Price_SI: already computed in Step 4; impute missing      │
│    via ffill/bfill within retailer                              │
│                                                                 │
│  Promo_Depth_SI = (Price_SI / Base_Price_SI) − 1               │
│    Range: −0.80 to +0.50 (clipped)                              │
│    Negative = discount; ~0 = no promo                           │
│                                                                 │
│  Output columns: Base_Price_SI (cleaned), Promo_Depth_SI        │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 11: LOG TRANSFORMATIONS                                  │
│  _create_features()                                             │
│                                                                 │
│  Log_Volume_Sales_SI = ln(Volume_Sales_SI)                      │
│  Log_Price_SI        = ln(Price_SI)                             │
│  Log_Base_Price_SI   = ln(Base_Price_SI)                        │
│  Log_Price_PL        = ln(Price_PL) where PL > 0; else 0.0     │
│                                                                 │
│  Output columns: Log_Volume_Sales_SI, Log_Price_SI,             │
│                  Log_Base_Price_SI, Log_Price_PL                 │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 12: MODEL CONTROL MASKS                                  │
│  _handle_missing_features()                                     │
│                                                                 │
│  Per retailer (from config.retailers):                           │
│                                                                 │
│  Retailer    has_promo    has_competitor                         │
│  ─────────   ─────────   ──────────────                         │
│  BJ's        1           1                                      │
│  Sam's Club  1           1                                      │
│  Costco      1           0                                      │
│                                                                 │
│  When has_competitor=0:                                          │
│    Price_PL → 0.0, Volume_Sales_PL → 0.0, Log_Price_PL → 0.0   │
│                                                                 │
│  Output columns: has_promo, has_competitor                       │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
               ┌──────────────────────┐
               │  FINAL OUTPUT:       │
               │  DataFrame           │
               │  ~467 rows × ~20 cols│
               │  (saved as           │
               │   prepared_data.csv) │
               └──────────────────────┘
```

---

## PART 3: WHAT THE MODEL ACTUALLY CONSUMES

### 3.1 Column-to-Parameter Mapping (Hierarchical Model — V2 Dual Elasticity)

This is the actual linear predictor built in `HierarchicalBayesianModel._build_model()`:

```
ln(Volume_Sales_SI) =   intercept[r]
                       + base_elasticity[r]  × ln(Base_Price_SI)
                       + promo_elasticity[r] × (Promo_Depth_SI × has_promo)
                       + elasticity_cross    × (ln(Price_PL) × has_competitor)
                       + β_spring            × Spring
                       + β_summer            × Summer
                       + β_fall              × Fall
                       + β_time              × Week_Number
                       + ε

where r ∈ {BJ's, Sam's Club, Costco}  (retailer index)
      ε ~ Normal(0, σ²)
```

| DataFrame Column | Model Variable | Parameter | Pooling | Prior (default) |
|---|---|---|---|---|
| `Log_Volume_Sales_SI` | `y` (observed) | — | — | — |
| `Log_Base_Price_SI` | `X_base` | `base_elasticity[r]` | **Partial** (per-retailer, pooled toward `mu_global_base`) | N(−2.0, 0.5) |
| `Promo_Depth_SI` | `X_promo` | `promo_elasticity[r]` | **Partial** (per-retailer, pooled toward `mu_global_promo`) | N(−4.0, 1.0) |
| `has_promo` | `X_has_promo` | — (mask) | — | — |
| `Log_Price_PL` | `X_cross` | `elasticity_cross` | **Complete** (shared across retailers) | N(0.15, 0.15) |
| `has_competitor` | `X_has_competitor` | — (mask) | — | — |
| `Spring` | `X_spring` | `beta_spring` | **Complete** (shared) | N(0.0, 0.2) |
| `Summer` | `X_summer` | `beta_summer` | **Complete** (shared) | N(0.0, 0.2) |
| `Fall` | `X_fall` | `beta_fall` | **Complete** (shared) | N(0.0, 0.2) |
| `Week_Number` | `X_time` | `beta_time` | **Complete** (shared) | N(0.0, 0.01) |
| `Retailer` | `group_idx` | `intercept[r]` | **Partial** (per-retailer, pooled toward `mu_global_intercept`) | N(10.0, 2.0) |

### 3.2 Hierarchical Structure

```
                    ┌──────────────────┐
                    │  POPULATION LEVEL │
                    │  (global priors)  │
                    └────────┬─────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
    mu_global_base    mu_global_promo   mu_global_intercept
    σ_group_base      σ_group_promo     σ_group_intercept
              │              │              │
              ▼              ▼              ▼
         ┌─────────────────────────────────────┐
         │          RETAILER LEVEL              │
         │  (partial pooling — shrinkage)       │
         └─────────┬───────────┬───────────┬───┘
                   │           │           │
                   ▼           ▼           ▼
              base_elast[0] base_elast[1] base_elast[2]
              promo_elast[0] promo_elast[1] promo_elast[2]
              intercept[0]  intercept[1]  intercept[2]
                   │           │           │
                   ▼           ▼           ▼
                 BJ's      Sam's Club   Costco

    Shared (not hierarchical):
      elasticity_cross, β_spring, β_summer, β_fall, β_time, σ
```

### 3.3 How Costco's Missing Data Is Handled

```
Costco row:  has_competitor = 0, Log_Price_PL = 0.0

In the linear predictor:
  elasticity_cross × (Log_Price_PL × has_competitor)
= elasticity_cross × (0.0 × 0)
= 0                                    ← cross-price term zeroed out

But Costco's base_elasticity[2] and promo_elasticity[2] are still
estimated — they're "borrowed" from BJ's and Sam's via partial pooling
toward the global mean (mu_global_base, mu_global_promo).
```

### 3.4 Time Trend

Both the Simple and Hierarchical models include `beta_time × Week_Number` in the linear predictor. This is a shared (not group-specific) parameter that captures any secular volume trend independent of price, promotions, and seasonality. The default prior N(0, 0.01) is intentionally tight — with ~160 weeks, even a small coefficient compounds to a meaningful annualized effect.

---

## PART 4: MCMC → POSTERIOR → BUSINESS OUTPUTS

### 4.1 Sampling

```
run_analysis.py calls model.fit(data)
    │
    ▼
bayesian_models.py → pm.sample()
    draws      = 2000   (per chain)
    tune       = 1000   (burn-in, discarded)
    chains     = 4
    target_accept = 0.95
    │
    ▼
Output: InferenceData (ArviZ trace object)
    posterior['base_elasticity']   shape: (4 chains, 2000 draws, 3 retailers)
    posterior['promo_elasticity']  shape: (4 chains, 2000 draws, 3 retailers)
    posterior['elasticity_cross']  shape: (4 chains, 2000 draws)
    posterior['beta_spring']       shape: (4 chains, 2000 draws)
    posterior['beta_summer']       shape: (4 chains, 2000 draws)
    posterior['beta_fall']         shape: (4 chains, 2000 draws)
    posterior['beta_time']         shape: (4 chains, 2000 draws)
    posterior['intercept']         shape: (4 chains, 2000 draws, 3 retailers)
    posterior['sigma']             shape: (4 chains, 2000 draws)
    posterior['mu_global_base']    shape: (4 chains, 2000 draws)
    posterior['mu_global_promo']   shape: (4 chains, 2000 draws)
    posterior['sigma_group_base']  shape: (4 chains, 2000 draws)
    posterior['sigma_group_promo'] shape: (4 chains, 2000 draws)
```

### 4.2 Convergence Diagnostics

```
BayesianResults._check_convergence():

    R-hat (max across all parameters)  → rhat_max    (should be < 1.01)
    ESS   (min across all parameters)  → ess_min     (should be > 400)
    Divergences (sum across all chains) → n_divergences (should be 0)

    converged = (rhat_max < 1.01) AND (ess_min > 400) AND (n_divergences == 0)
```

### 4.3 Posterior Summary Extraction

For each parameter, `_extract_posteriors()` computes:

```
samples = trace.posterior[param].values.flatten()   # 4 × 2000 = 8000 samples

PosteriorSummary:
    mean     = samples.mean()
    median   = np.median(samples)
    std      = samples.std()
    ci_lower = np.percentile(samples, 2.5)     # 95% credible interval
    ci_upper = np.percentile(samples, 97.5)
```

### 4.4 Revenue Impact Formulas

These are the formulas that produce the final dollar-relevant business outputs.

#### Base Price Impact (`results.base_price_impact(price_change_pct)`)

```python
# For each of the 8000 posterior samples of base_elasticity:

volume_impact_pct = base_elasticity_sample × price_change_pct

revenue_multiplier = (1 + volume_impact_pct / 100) × (1 + price_change_pct / 100)

revenue_impact_pct = (revenue_multiplier − 1) × 100

# Outputs (across all 8000 samples):
#   volume_impact_mean       = mean(volume_impact_pct)
#   volume_impact_ci         = [percentile(2.5), percentile(97.5)]
#   revenue_impact_mean      = mean(revenue_impact_pct)
#   revenue_impact_ci        = [percentile(2.5), percentile(97.5)]
#   probability_positive     = fraction of samples where revenue_impact > 0
```

**Example:** If `base_elasticity = −2.0` and `price_change = +5%`:
- Volume impact = −2.0 × 5 = −10%
- Revenue multiplier = (1 − 0.10) × (1 + 0.05) = 0.90 × 1.05 = 0.945
- Revenue impact = −5.5%

#### Promotional Impact (`results.promo_impact(discount_depth_pct)`)

```python
# discount_depth_pct is positive (e.g., 10 means 10% off)
price_change_pct = −abs(discount_depth_pct)

# For each of the 8000 posterior samples of promo_elasticity:

volume_impact_pct = promo_elasticity_sample × price_change_pct
# (negative × negative = positive volume lift)

revenue_multiplier = (1 + volume_impact_pct / 100) × (1 + price_change_pct / 100)

revenue_impact_pct = (revenue_multiplier − 1) × 100

# Same output structure as base price impact
```

**Example:** If `promo_elasticity = −4.0` and `discount_depth = 15%`:
- Volume impact = −4.0 × (−15) = +60%
- Revenue multiplier = (1 + 0.60) × (1 − 0.15) = 1.60 × 0.85 = 1.36
- Revenue impact = +36%

#### Elasticity Comparison (`results.compare_elasticities()`)

```python
ratio = |promo_elasticity_samples| / |base_elasticity_samples|   # element-wise

# Outputs:
#   multiplier_mean                = mean(ratio)
#   multiplier_ci                  = [percentile(2.5), percentile(97.5)]
#   probability_promo_more_responsive = fraction where |promo| > |base|
```

---

## PART 5: VISUALIZATION CONSUMPTION MAP

### 5.1 What Each Plot Reads

| Plot Function | From `results` Object | From `data` DataFrame |
|---|---|---|
| `plot_trace()` | `trace.posterior[base_elasticity, promo_elasticity, elasticity_cross, beta_spring, beta_summer, beta_fall]` | — |
| `plot_posteriors()` | `.base_elasticity`, `.promo_elasticity`, `.elasticity_cross`, `.beta_promo`, `.seasonal_effects` + raw trace samples | — |
| `plot_seasonal_patterns()` | `.seasonal_effects` (means + CIs) | `Date`, `Volume_Sales_SI` (monthly grouping) |
| `plot_time_trend()` | `.beta_time_trend` (mean + CI) + raw trace `beta_time` samples | `Date`, `Volume_Sales_SI`, `Retailer` (time series by retailer with 8-week rolling avg) |
| `plot_base_vs_promo_comparison()` | `.base_elasticity`, `.promo_elasticity` (means + CIs) | — |
| `plot_revenue_scenarios_base()` | calls `results.base_price_impact()` for each scenario | — |
| `plot_revenue_scenarios_promo()` | calls `results.promo_impact()` for each discount | — |
| `plot_group_comparison()` | `.group_elasticities`, `.global_elasticity`, trace posterior `base_elasticity` by group index | — |
| `generate_html_report()` | All of the above + `.converged`, `.rhat_max`, `.ess_min`, `.n_divergences`, `.beta_time_trend` (annualized interpretation) | `len(data)` for observation count |

### 5.2 HTML Report Revenue Tables

```
Base Price Table (always generated):
    For each price_change ∈ [-5, -3, -1, +1, +3, +5]:
        results.revenue_impact(price_change) → volume%, revenue%, P(positive)

Promo Table (generated only if promo_elasticity exists):
    For each discount ∈ [5, 10, 15, 20]:
        results.promo_impact(discount) → volume%, revenue%, P(positive)
```

---

## PART 6: COMPLETE COLUMN FATE SUMMARY

### 6.1 Columns That Reach the Model

| # | Column | Origin | Enters Model As | Role |
|---|---|---|---|---|
| 1 | `Log_Volume_Sales_SI` | ln(`Volume Sales` or `Unit Sales × factor`) | `y` (observed) | **Dependent variable** |
| 2 | `Log_Base_Price_SI` | ln(`Base Dollar Sales / Base Unit Sales` or `Non Promoted $ / Non Promoted Units`) | `X_base` | Base price elasticity predictor |
| 3 | `Promo_Depth_SI` | (`Price_SI / Base_Price_SI`) − 1 | `X_promo` | Promotional elasticity predictor |
| 4 | `Log_Price_PL` | ln(`PL Dollar Sales / PL Unit Sales`) or 0.0 | `X_cross` | Cross-price elasticity predictor |
| 5 | `has_competitor` | Config: 1 (BJ's, Sam's), 0 (Costco) | `X_has_competitor` | Mask — zeros out cross-price for Costco |
| 6 | `has_promo` | Config: 1 (all three) | `X_has_promo` | Mask — zeros out promo for retailers without promo data |
| 7 | `Spring` | 1 if Month ∈ {3,4,5} | `X_spring` | Seasonality dummy |
| 8 | `Summer` | 1 if Month ∈ {6,7,8} | `X_summer` | Seasonality dummy |
| 9 | `Fall` | 1 if Month ∈ {9,10,11} | `X_fall` | Seasonality dummy |
| 10 | `Week_Number` | `data_prep._add_time_features()` | `X_time` | Time trend predictor |
| 11 | `Retailer` | Hardcoded label per file | `group_idx` | Hierarchical grouping variable |

### 6.2 Columns Used by Visualizations Only (Not in Model)

| # | Column | Used By |
|---|---|---|
| 11 | `Date` | `plot_seasonal_patterns()`, `plot_time_trend()` — monthly/weekly grouping |
| 12 | `Volume_Sales_SI` | `plot_seasonal_patterns()`, `plot_time_trend()` — monthly average / rolling average |
| 12a | `Retailer` | `plot_time_trend()` — color-coded time series per retailer (also used as model grouping variable) |

### 6.3 Columns Created but NEVER Consumed (by model or visualizations)

| # | Column | Created In | Why Unused |
|---|---|---|---|
| 13 | `Month` | `data_prep._add_seasonal_features()` | Intermediate; only used to derive Spring/Summer/Fall |
| 14 | `Price_SI` | `data_prep._pivot_to_wide()` | Log version used instead |
| 15 | `Base_Price_SI` | `data_prep._add_base_and_promo_depth()` | Log version used instead; also used to derive Promo_Depth_SI |
| 16 | `Price_PL` | `data_prep._pivot_to_wide()` | Log version used instead |
| 17 | `Volume_Sales_PL` | `data_prep._pivot_to_wide()` | Never consumed anywhere |
| 18 | `Log_Price_SI` | `data_prep._create_features()` | V1 fallback only; V2 uses Log_Base_Price_SI |
| 19 | `Promo_Intensity_SI` | `data_prep._pivot_to_wide()` | V1 fallback only; V2 uses Promo_Depth_SI |

### 6.4 Enhanced Features Described in Mapping Doc but NEVER Created

The `data_prep.py` has public methods for these, but `run_analysis.py` never calls them:

| Feature | Method Available | Would Require |
|---|---|---|
| `Price_x_Spring` | `prep.add_interaction_term(df, 'Log_Price_SI', 'Spring')` | Call after `transform()` |
| `Price_x_Summer` | `prep.add_interaction_term(df, 'Log_Price_SI', 'Summer')` | Call after `transform()` |
| `Log_Price_SI_lag1` | `prep.add_lagged_feature(df, 'Log_Price_SI', [1], group_by=['Retailer'])` | Call after `transform()` |
| `Log_Price_SI_lag4` | `prep.add_lagged_feature(df, 'Log_Price_SI', [4], group_by=['Retailer'])` | Call after `transform()` |
| `Price_SI_ma4` | `prep.add_moving_average(df, 'Price_SI', [4], group_by=['Retailer'])` | Call after `transform()` |
| `Price_SI_ma8` | `prep.add_moving_average(df, 'Price_SI', [8], group_by=['Retailer'])` | Call after `transform()` |
| `Price_Gap` | `prep.add_custom_feature(df, 'Price_Gap', lambda d: d['Price_SI'] - d['Price_PL'])` | Call after `transform()` |
| `Price_Index` | `prep.add_custom_feature(df, 'Price_Index', lambda d: d['Price_SI'] / d['Price_SI_ma4'])` | Requires `Price_SI_ma4` first |
| `Log_Price_Gap` | `prep.add_custom_feature(df, 'Log_Price_Gap', lambda d: np.log(d['Price_Gap']))` | Requires `Price_Gap` first |

Even if created, none of these are consumed by `bayesian_models.py`. They would require model code changes to enter the linear predictor.

---

## PART 7: END-TO-END TRACE — ONE COMPLETE EXAMPLE

### Tracing a single BJ's row from raw CSV to revenue impact:

```
RAW CSV ROW (bjs.csv):
  Time = "Week Ending 06-15-24"
  Product = "SPARKLING ICE BASE-BOTTLED WATER-..."
  Dollar Sales = 45,000
  Unit Sales = 3,000
  Volume Sales = 6,200
  Base Dollar Sales = 48,000
  Base Unit Sales = 3,100
  Unit Sales Any Merch = 800
  Unit Sales Feature Only = 200

Step 1-2: Load, filter → Product_Short = "Sparkling Ice", Retailer = "BJ's"

Step 3: Date = 2024-06-15

Step 4: Avg_Price = 45000/3000 = $15.00
        Base_Avg_Price = 48000/3100 = $15.48

Step 5: Volume Sales = 6,200 (direct)

Step 6: Promo_Intensity = (800+200+0+0)/3000 = 0.333

Step 7: Pivot → Volume_Sales_SI=6200, Price_SI=$15.00, Base_Price_SI=$15.48

Step 8: Week_Number = (2024-06-15 − 2023-01-01).days / 7 = 76

Step 9: Month=6, Spring=0, Summer=1, Fall=0

Step 10: Promo_Depth_SI = (15.00/15.48) − 1 = −0.031  (3.1% discount)

Step 11: Log_Volume_Sales_SI = ln(6200) = 8.733
         Log_Base_Price_SI = ln(15.48) = 2.738
         Log_Price_SI = ln(15.00) = 2.708
         Log_Price_PL = ln(PL_price)  [from PL row for same date]

Step 12: has_promo=1, has_competitor=1

MODEL CONSUMPTION (this row contributes to likelihood):
  y     = 8.733
  X_base = 2.738   × base_elasticity[BJs]
  X_promo = −0.031 × 1 × promo_elasticity[BJs]
  X_cross = Log_Price_PL × 1 × elasticity_cross
  X_summer = 1 × β_summer
  X_time = 76 × β_time
  ε ~ Normal(0, σ²)

POST-SAMPLING:
  If posterior mean base_elasticity[BJs] = −1.8
  Then: a +3% base price increase →
    Volume impact = −1.8 × 3 = −5.4%
    Revenue multiplier = (1 − 0.054) × (1.03) = 0.974
    Revenue impact = −2.6%
    P(revenue positive) = fraction of 8000 samples where impact > 0
```

---

## PART 8: FILE OUTPUT MAP

```
run_analysis.py generates:
│
├── results/
│   ├── prepared_data.csv          ← DataFrame after data_prep.transform()
│   ├── model_summary.txt          ← results.summary() text
│   ├── results_summary.csv        ← base/promo/cross elasticity means + CIs
│   ├── trace.nc                   ← full ArviZ InferenceData (NetCDF)
│   ├── analysis.log               ← pipeline log
│   │
│   ├── plots/
│   │   ├── trace.png              ← MCMC trace diagnostics (now includes beta_time)
│   │   ├── posteriors.png         ← posterior distributions (now includes beta_time)
│   │   ├── seasonal.png           ← monthly sales + seasonal effects
│   │   ├── time_trend.png         ← volume over time by retailer + beta_time posterior
│   │   ├── revenue_base.png       ← base price revenue scenarios
│   │   ├── revenue_promo.png      ← promo discount revenue scenarios
│   │   ├── base_vs_promo.png      ← side-by-side elasticity comparison
│   │   └── groups.png             ← retailer-specific elasticities
│   │
│   ├── trace_plot.png             ← (duplicate, for HTML report)
│   ├── posterior_plot.png         ← (duplicate, for HTML report)
│   ├── seasonal_plot.png          ← (duplicate, for HTML report)
│   ├── time_trend_plot.png        ← (duplicate, for HTML report)
│   ├── revenue_scenarios_base.png ← (duplicate, for HTML report)
│   ├── revenue_scenarios_promo.png← (duplicate, for HTML report)
│   ├── base_vs_promo_comparison.png ← (duplicate, for HTML report)
│   ├── group_comparison.png       ← (duplicate, for HTML report)
│   │
│   └── elasticity_report.html     ← self-contained HTML report
```
