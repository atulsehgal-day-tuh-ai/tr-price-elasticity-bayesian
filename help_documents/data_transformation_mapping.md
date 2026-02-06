# Data Transformation Mapping: Raw Inputs → Model-Ready Output

**Prepared for:** Atul Sehgal
**Date:** February 6, 2026
**Purpose:** Complete field-level traceability from three raw retailer CSV files to the `enhanced_data.csv` used in the Bayesian Price Elasticity model.

---

## 1. Source Files

| File | Provider | Rows | Columns | Products | Time Span | Skip Rows |
|------|----------|------|---------|----------|-----------|-----------|
| `bjs.csv` | Circana | 477 | 74 | 2 (Sparkling Ice + Private Label) | Jan 2023 – Jan 2026 | 2 (title + geography) |
| `sams.csv` | Circana | 477 | 74 | 2 (Sparkling Ice + Private Label) | Jan 2023 – Jan 2026 | 2 (title + geography) |
| `costco.csv` | Costco CRX | 1,932 | 23 | 12 (1 brand aggregate + 11 UPCs) | Jan 2023 – Jan 2026 | 1 (title row) |

## 2. Output File

| Property | Value |
|----------|-------|
| File | `enhanced_data.csv` |
| Rows | 467 (Costco: 157, BJ's: 155, Sam's Club: 155) |
| Columns | 30 |
| Grain | Retailer × Week |
| Row reduction | ~4 rows per retailer lost to lag-4 feature warmup window |

---

## 3. Pre-Processing Steps

### 3.1 File Loading

| Retailer | Load Command | Header Row |
|----------|-------------|------------|
| BJ's | `pd.read_csv('bjs.csv', skiprows=2)` | Row 3 |
| Sam's Club | `pd.read_csv('sams.csv', skiprows=2)` | Row 3 |
| Costco | `pd.read_csv('costco.csv', skiprows=1)` | Row 2 |

### 3.2 Product Filtering

| Retailer | Filter Column | Filter Value | Rows Retained |
|----------|--------------|--------------|---------------|
| BJ's (SI) | `Product` | `SPARKLING ICE BASE-BOTTLED WATER-SELTZER/SPARKLING/MINERAL WATER` | 159 |
| BJ's (PL) | `Product` | `PRIVATE LABEL-BOTTLED WATER-SELTZER/SPARKLING/MINERAL WATER` | 318 |
| Sam's (SI) | `Product` | `SPARKLING ICE BASE-BOTTLED WATER-SELTZER/SPARKLING/MINERAL WATER` | 159 |
| Sam's (PL) | `Product` | `PRIVATE LABEL-BOTTLED WATER-SELTZER/SPARKLING/MINERAL WATER` | 318 |
| Costco | `Item` | `Sparkling Ice Core 17oz 24ct 2023 through 2025 Items` | 161 |

The 11 individual Costco UPC-level rows are discarded. The brand aggregate is a verified exact sum of all 11 UPCs.

### 3.3 Date Parsing

| Retailer | Raw Format | Example | Parse Logic |
|----------|-----------|---------|-------------|
| BJ's / Sam's | `Week Ending MM-DD-YY` | `Week Ending 01-08-23` | Strip prefix → `pd.to_datetime(format='%m-%d-%y')` |
| Costco | `N week ending MM-DD-YYYY` | `1 week ending 01-08-2023` | Regex extract after `ending ` → `pd.to_datetime(format='%m-%d-%Y')` |

---

## 4. Column-by-Column Mapping (All 30 Output Columns)

### 4.1 Core Identity Columns

| # | Output Column | BJ's Source | Sam's Source | Costco Source | Transformation |
|---|--------------|-------------|-------------|---------------|----------------|
| 1 | `Date` | `Time` | `Time` | `Time` | Parsed per Section 3.3 |
| 2 | `Retailer` | — | — | — | Hardcoded: `"BJ's"`, `"Sam's Club"`, `"Costco"` |

### 4.2 Sparkling Ice Sales & Price Columns

| # | Output Column | BJ's / Sam's Source | Costco Source | Formula | Validation |
|---|--------------|-------------------|---------------|---------|------------|
| 3 | `Volume_Sales_SI` | `Volume Sales` (direct) | `Unit Sales` | BJ's/Sam's: direct column. Costco: `Unit Sales × 2.0` (24-pack = 2 Circana volume units of 204 oz each) | ✅ Exact match all retailers |
| 4 | `Price_SI` | `Dollar Sales` ÷ `Unit Sales` | `Avg Net Price` | BJ's/Sam's: Circana Dollar Sales already reflects transaction revenue. Costco: `Avg Net Price` is the true price paid after coupons. **Do NOT use** Costco `Dollar Sales / Unit Sales` — that gives shelf price, not price paid. | ✅ Exact match all retailers |
| 5 | `Base_Price_SI` | `Base Dollar Sales` ÷ `Base Unit Sales` | `Non Promoted Dollars` ÷ `Non Promoted Units` | BJ's/Sam's: Circana modeled base (estimated demand absent promos). Costco: actual non-promoted transactions. Fallback: `Average Price per Unit` when `Non Promoted Units` < 500. | ✅ Exact match all retailers |
| 6 | `Promo_Depth_SI` | (`Price_SI` ÷ `Base_Price_SI`) − 1 | (`Avg Net Price` ÷ NP Base Price) − 1 | Same formula for all retailers. Range: −0.275 (deep promo) to +0.001 (no promo). | ✅ Exact match all retailers |
| 7 | `Promo_Intensity_SI` | Derived from Circana merchandising columns | `0.0` (constant) | BJ's/Sam's: continuous [0, 1] measure of promotional activity breadth (correlated with promo depth, r ≈ 0.68–0.75). Costco: set to 0 — CRX data lacks equivalent merchandising intensity measures. | ✅ Costco = 0 confirmed |

### 4.3 Private Label Columns

| # | Output Column | BJ's / Sam's Source | Costco Source | Formula |
|---|--------------|-------------------|---------------|---------|
| 8 | `Volume_Sales_PL` | PL rows: `Volume Sales` | — | BJ's/Sam's: from Private Label product rows, joined by Date. Costco: `0.0` (no PL data). |
| 9 | `Price_PL` | PL rows: `Dollar Sales` ÷ `Unit Sales` | — | BJ's/Sam's: Private Label average price. Costco: `0.0`. |
| 10 | `Private Label` | PL rows: `Base Dollar Sales` ÷ `Base Unit Sales` | — | BJ's/Sam's: Private Label **base price** (Circana modeled). Costco: `NaN`. |

### 4.4 Time Features

| # | Output Column | Source | Formula |
|---|--------------|--------|---------|
| 11 | `Week_Number` | `Date` | `(Date − 2023-01-01).days ÷ 7` as integer. Monotonic time trend; consistent across retailers for the same week. |
| 12 | `Month` | `Date` | `Date.dt.month` (1–12) |

### 4.5 Seasonality Dummies

| # | Output Column | Formula |
|---|--------------|---------|
| 13 | `Spring` | `1` if Month ∈ {3, 4, 5}, else `0` |
| 14 | `Summer` | `1` if Month ∈ {6, 7, 8}, else `0` |
| 15 | `Fall` | `1` if Month ∈ {9, 10, 11}, else `0` |

Winter (Dec, Jan, Feb) is the reference category (all three dummies = 0).

### 4.6 Log Transformations

| # | Output Column | Formula | Purpose in Model |
|---|--------------|---------|-----------------|
| 16 | `Log_Volume_Sales_SI` | `ln(Volume_Sales_SI)` | Dependent variable (Y) |
| 17 | `Log_Price_SI` | `ln(Price_SI)` | Average price paid (log) |
| 18 | `Log_Base_Price_SI` | `ln(Base_Price_SI)` | Base price elasticity coefficient (β₁) |
| 19 | `Log_Price_PL` | `ln(Price_PL)` where PL > 0; `0.0` for Costco | Cross-price elasticity coefficient (β₃); masked by `has_competitor` |

### 4.7 Model Control Masks

| # | Output Column | BJ's | Sam's Club | Costco | Purpose |
|---|--------------|------|-----------|--------|---------|
| 20 | `has_promo` | `1` | `1` | `1` | All three retailers have promo depth data |
| 21 | `has_competitor` | `1` | `1` | `0` | Costco has no Private Label data; cross-price term zeroed out |

### 4.8 Interaction Terms

| # | Output Column | Formula | Purpose |
|---|--------------|---------|---------|
| 22 | `Price_x_Spring` | `Log_Price_SI × Spring` | Seasonal price sensitivity interaction |
| 23 | `Price_x_Summer` | `Log_Price_SI × Summer` | Seasonal price sensitivity interaction |

### 4.9 Lag Features (computed within-retailer)

| # | Output Column | Formula | Purpose |
|---|--------------|---------|---------|
| 24 | `Log_Price_SI_lag1` | `Log_Price_SI` shifted 1 week back (within retailer) | Price persistence / consumer reference price |
| 25 | `Log_Price_SI_lag4` | `Log_Price_SI` shifted 4 weeks back (within retailer) | Longer-term price memory |

These lags are computed per-retailer (not across retailers), which is why 4 rows are dropped per retailer from the beginning of the time series.

### 4.10 Moving Averages (computed within-retailer)

| # | Output Column | Formula | Purpose |
|---|--------------|---------|---------|
| 26 | `Price_SI_ma4` | 4-week rolling mean of `Price_SI` (within retailer) | Short-term price trend |
| 27 | `Price_SI_ma8` | 8-week rolling mean of `Price_SI` (within retailer) | Medium-term price trend |

### 4.11 Competitive Price Features

| # | Output Column | Formula | Purpose |
|---|--------------|---------|---------|
| 28 | `Price_Gap` | `Price_SI − Price_PL` | Absolute price difference vs. Private Label. Costco: equals `Price_SI` (since `Price_PL` = 0). |
| 29 | `Price_Index` | `Price_SI ÷ Price_SI_ma4` | Price relative to recent 4-week average; values > 1 indicate current price above recent trend. |
| 30 | `Log_Price_Gap` | `ln(Price_Gap)` | Log of absolute price gap. Costco: equals `Log_Price_SI`. |

---

## 5. Transformation Pipeline Summary

```
Step 1: LOAD
  bjs.csv     → skip 2 rows → 74-column DataFrame
  sams.csv    → skip 2 rows → 74-column DataFrame
  costco.csv  → skip 1 row  → 23-column DataFrame

Step 2: FILTER PRODUCTS
  BJ's/Sam's  → keep "SPARKLING ICE" rows (159 weeks) + "PRIVATE LABEL" rows
  Costco      → keep brand aggregate row only (161 weeks), discard 11 UPCs

Step 3: PARSE DATES
  BJ's/Sam's  → strip "Week Ending ", parse %m-%d-%y
  Costco      → regex extract after "ending ", parse %m-%d-%Y

Step 4: COMPUTE CORE METRICS (per retailer)
  Volume_Sales_SI:
    BJ's/Sam's  = Volume Sales (direct)
    Costco       = Unit Sales × 2.0

  Price_SI (avg price paid):
    BJ's/Sam's  = Dollar Sales / Unit Sales
    Costco       = Avg Net Price  ← CRITICAL: NOT Dollar Sales / Unit Sales

  Base_Price_SI (regular/non-promoted price):
    BJ's/Sam's  = Base Dollar Sales / Base Unit Sales
    Costco       = Non Promoted Dollars / Non Promoted Units
                   (fallback: Average Price per Unit if NP Units < 500)

  Promo_Depth_SI = (Price_SI / Base_Price_SI) − 1

Step 5: JOIN PRIVATE LABEL (BJ's/Sam's only)
  Join PL product rows by Date to get Price_PL, Volume_Sales_PL, Private Label (base price)
  Costco: set all PL fields to 0 or NaN

Step 6: ASSIGN RETAILER & MASKS
  Retailer     = "BJ's" / "Sam's Club" / "Costco"
  has_promo    = 1 (all retailers)
  has_competitor = 1 (BJ's, Sam's) / 0 (Costco)

Step 7: TIME FEATURES
  Week_Number  = (Date − 2023-01-01).days / 7
  Month, Spring, Summer, Fall from Date

Step 8: LOG TRANSFORMATIONS
  ln(Volume_Sales_SI), ln(Price_SI), ln(Base_Price_SI), ln(Price_PL)
  Costco Log_Price_PL = 0.0

Step 9: ENHANCED FEATURES (within-retailer)
  Lag features:     Log_Price_SI_lag1, Log_Price_SI_lag4
  Moving averages:  Price_SI_ma4, Price_SI_ma8
  Interactions:     Price_x_Spring, Price_x_Summer
  Competitive:      Price_Gap, Price_Index, Log_Price_Gap
  Promo breadth:    Promo_Intensity_SI

Step 10: DROP WARMUP ROWS
  Remove first 4 rows per retailer (lag-4 warmup)
  Final: 157 + 155 + 155 = 467 rows

Step 11: COMBINE & EXPORT
  Stack all three retailers → enhanced_data.csv (467 × 30)
```

---

## 6. Validation Results

All tests below were run comparing `enhanced_data.csv` back to the three raw source files.

### 6.1 Core Field Accuracy (all exact-match, max difference = 0.000000)

| Test | BJ's | Sam's | Costco |
|------|------|-------|--------|
| Volume_Sales_SI | ✅ Exact | ✅ Exact | ✅ Exact |
| Price_SI | ✅ Exact | ✅ Exact | ✅ Exact |
| Base_Price_SI | ✅ Exact | ✅ Exact | ✅ Exact |
| Promo_Depth_SI | ✅ Exact | ✅ Exact | ✅ Exact |
| Price_PL | ✅ Exact | ✅ Exact | ✅ Zero |
| Private Label (PL base price) | ✅ Exact | ✅ Exact | ✅ NaN |

### 6.2 Derived Feature Accuracy (all exact-match)

| Feature | Max Difference | Status |
|---------|---------------|--------|
| Log_Volume_Sales_SI | 0.000000 | ✅ |
| Log_Base_Price_SI | 0.000000 | ✅ |
| Log_Price_SI | 0.000000 | ✅ |
| Spring / Summer / Fall | Exact boolean match | ✅ |
| Price_x_Spring | 0.000000 | ✅ |
| Price_x_Summer | 0.000000 | ✅ |
| Log_Price_SI_lag1 (within-retailer) | 0.000000 | ✅ |
| Log_Price_SI_lag4 (within-retailer) | 0.000000 | ✅ |
| Price_SI_ma4 (within-retailer) | 0.000000 | ✅ |
| Price_SI_ma8 (within-retailer) | 0.000000 | ✅ |
| Price_Gap = Price_SI − Price_PL | 0.000000 | ✅ |
| Log_Price_Gap = ln(Price_Gap) | 0.000000 | ✅ |
| Price_Index = Price_SI / Price_SI_ma4 | 0.000000 | ✅ |

### 6.3 Structural Checks

| Check | Expected | Actual | Status |
|-------|----------|--------|--------|
| Duplicate Date-Retailer pairs | 0 | 0 | ✅ |
| Costco `has_promo` | All 1 | All 1 | ✅ |
| Costco `has_competitor` | All 0 | All 0 | ✅ |
| BJ's/Sam's `has_competitor` | All 1 | All 1 | ✅ |
| Costco `Log_Price_PL` | All 0.0 | All 0.0 | ✅ |
| Costco `Volume_Sales_SI` > 0 | All rows | All rows | ✅ |
| Week_Number consistent across retailers (same date) | Same value | Same value | ✅ |

### 6.4 Value Range Checks (Costco)

| Metric | Expected Range | Actual Range | Status |
|--------|---------------|--------------|--------|
| Base_Price_SI | $15.50 – $18.50 | $15.74 – $18.05 | ✅ |
| Promo_Depth_SI | −0.30 to +0.001 | −0.275 to +0.001 | ✅ |
| Non-promo weeks (|depth| < 1%) | ~102 | 104 | ✅ |
| Promo weeks (depth < −1%) | ~59 | 53 | ✅ |

---

## 7. Critical Design Decisions

### 7.1 Costco `Price_SI` Uses `Avg Net Price`, Not `Dollar Sales / Unit Sales`

Costco's `Dollar Sales` represents gross revenue at shelf price (pre-coupon), unlike Circana where `Dollar Sales` reflects actual transaction revenue. Using `Dollar Sales / Unit Sales` for Costco would yield ~$16.02 every week regardless of promotions, making promo depth ≈ 0 and breaking the elasticity model. `Avg Net Price` correctly captures the blended price consumers actually paid.

### 7.2 Costco `Base_Price_SI` Uses Non-Promoted Transactions, Not Shelf Price

`Non Promoted Dollars / Non Promoted Units` captures the actual price at which non-promoted units transacted — conceptually aligned with Circana's modeled base price (estimated demand absent promos). `Average Price per Unit` (shelf/list price) is the fallback for weeks where NP Units < 500, but all 161 weeks in the current data have sufficient NP units.

### 7.3 Costco Private Label Is Absent

CRX data contains no Private Label products. The model handles this via `has_competitor = 0`, which zeros out the cross-price term (β₃ × Log_Price_PL). In the hierarchical model, Costco's cross-price elasticity is "borrowed" from BJ's and Sam's through partial pooling.

### 7.4 Costco `Promo_Intensity_SI` Is Set to Zero

BJ's and Sam's have Circana merchandising columns (ACV distribution, store-level merch activity) that support computing a continuous promotional intensity measure. Costco's CRX data lacks equivalent measures, so `Promo_Intensity_SI = 0` for all Costco rows. Promo effects at Costco are captured entirely through `Promo_Depth_SI`.

### 7.5 Week_Number Origin

`Week_Number` is computed as weeks since January 1, 2023 (not `min(Date)` as noted in the contract pseudocode). This is functionally equivalent — it produces a monotonic integer time trend consistent across all three retailers for any given week. The only effect is shifting the model intercept (β₀) by a constant; trend coefficients are unaffected.

---

## 8. Raw Source Column Usage Summary

### 8.1 BJ's / Sam's (Circana) — 74 Columns Available, 8 Used

| Source Column | Maps To | Used For |
|--------------|---------|----------|
| `Product` | — | Row filtering (SI vs PL) |
| `Time` | `Date` | Date parsing |
| `Dollar Sales` | `Price_SI` | Numerator of avg price (SI rows); `Price_PL` (PL rows) |
| `Unit Sales` | `Price_SI` | Denominator of avg price (SI rows); `Price_PL` (PL rows) |
| `Volume Sales` | `Volume_Sales_SI` | Direct column (SI rows); `Volume_Sales_PL` (PL rows) |
| `Base Dollar Sales` | `Base_Price_SI` | Numerator of base price (SI rows); `Private Label` (PL rows) |
| `Base Unit Sales` | `Base_Price_SI` | Denominator of base price (SI rows); `Private Label` (PL rows) |
| Merchandising columns | `Promo_Intensity_SI` | Promotional activity breadth measure |

66 Circana columns are not directly used in the model-ready output (Year Ago comparisons, Feature/Display breakdowns, store counts, ACV distribution, etc.).

### 8.2 Costco (CRX) — 23 Columns Available, 5 Used

| Source Column | Maps To | Used For |
|--------------|---------|----------|
| `Item` | — | Row filtering (brand aggregate only) |
| `Time` | `Date` | Date parsing |
| `Unit Sales` | `Volume_Sales_SI` | `Unit Sales × 2.0` |
| `Non Promoted Dollars` | `Base_Price_SI` | Numerator of NP base price |
| `Non Promoted Units` | `Base_Price_SI` | Denominator of NP base price |
| `Avg Net Price` | `Price_SI` | Direct column — actual blended price paid |
| `Average Price per Unit` | — | Fallback for Base_Price_SI when NP Units < 500 (not triggered in current data) |

16 Costco columns are not used (Venue, Warehouses Selling, Item Description/Number/UPC, Average Coupon Value, Average Promoted Price, % Discount, Dollar Sales, Net Dollars, Promoted Dollars/Units, Total Discount Dollars, OOS %).

---

## 9. Model Equation Reference

The transformed columns feed the following hierarchical Bayesian model:

```
ln(Volume_Sales_SI) = β₀
                    + β₁ · ln(Base_Price_SI)          ← base price elasticity
                    + β₂ · Promo_Depth_SI              ← promotional elasticity
                    + β₃ · ln(Price_PL) · has_competitor ← cross-price (masked for Costco)
                    + β₄ · Spring + β₅ · Summer + β₆ · Fall  ← seasonality
                    + β₇ · Week_Number                  ← time trend
                    + ε

With retailer-level random effects on β₁, β₂, β₃ and partial pooling across
BJ's, Sam's Club, and Costco.
```

Enhanced features (lags, moving averages, interactions, Price_Gap, Price_Index) are available for model extensions and diagnostics.
