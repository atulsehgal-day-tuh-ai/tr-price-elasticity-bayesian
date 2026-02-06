# Costco Data Integration Contract
## Mapping Costco CRX Data to the Bayesian Price Elasticity Pipeline

**Prepared for:** Atul Sehgal — Director of Data Science, Swire Coca-Cola  
**Date:** February 5, 2026  
**Version:** 1.2  
**Purpose:** Document every data transformation decision required to integrate Costco into the existing BJ's/Sam's Bayesian price elasticity system, so that a single hierarchical model can be run across all three retailers.

---

## 1. Context and Objective

The existing Bayesian Price Elasticity Analysis System (v2.0) runs on Circana retail data for **BJ's** and **Sam's Club**. Both files share an identical 74-column schema. The system produces dual elasticities (base price + promotional) via a hierarchical Bayesian model with partial pooling across retailers.

**Costco** uses a different data source — the **CRX (Costco Retail Extract)** system — with a 23-column schema, different column names, different price/promo concepts, and no Private Label data. This document specifies exactly how each Costco field maps to the model-ready format so the three retailers can be combined into a single hierarchical model.

**Goal:** After transformation, a Costco row should be indistinguishable from a BJ's or Sam's row in the model-ready DataFrame.

---

## 2. Source Data Comparison: BJ's/Sam's vs Costco

### 2.1 File-Level Differences

| Dimension | BJ's / Sam's (Circana) | Costco (CRX) |
|---|---|---|
| **Data provider** | Circana (formerly IRI) | Costco's internal CRX system |
| **Header rows to skip** | 2 (title row + geography row) | 1 (title row only) |
| **Column count** | 74 | 23 |
| **Column header row** | Row 3 | Row 2 |
| **Product identifier column** | `Product` | `Item` |
| **Product values** | 2: Sparkling Ice + Private Label | 12: 1 brand aggregate + 11 individual UPCs |
| **Private Label data** | ✅ Present (separate rows in same file) | ❌ Not available |
| **Volume Sales column** | ✅ Direct column | ❌ Missing — must be computed |
| **Base sales columns** | ✅ `Base Dollar Sales`, `Base Unit Sales` | ❌ Not present — different promo structure |
| **Promo data** | Implicit (derived from base vs total) | Explicit (promoted $, units, coupon value, etc.) |
| **Date format** | `Week Ending 01-08-23` | `1 week ending 01-08-2023` |
| **Geography** | Row 2 header (e.g., `Geography:BJ's Corp-RMA - Club`) | `Venue` column (`Total US by Region`) |
| **Weeks of data** | 159 per product (Jan 2023 – Jan 2026) | 161 per item (Jan 2023 – Jan 2026) |

### 2.2 Costco Column Inventory (all 23 columns in CSV)

| # | Column Name | Data Dictionary Definition | Used in Mapping? |
|---|---|---|---|
| 1 | `Venue` | Geography/location dimension | No — hardcode retailer as "Costco" |
| 2 | `Item` | Product identifier (brand aggregate or individual UPC) | **Yes** — filter to brand-level aggregate |
| 3 | `Time` | Weekly date | **Yes** — parse to date |
| 4 | `Dollar Sales` | Gross Dollar Sales net of Returns (but **includes coupons at shelf price**) | **Yes** — but NOT used for avg price (see Section 4.4) |
| 5 | `Unit Sales` | Unit Sales net of Returns | **Yes** — for Volume Sales computation |
| 6 | `Warehouses Selling` | Count of warehouses with sales that week | No |
| 7 | `Average Price per Unit` | Regular price of an item — will reflect any competitive price match (i.e., **shelf/list price**) | **Yes** — fallback for Base Price when NP Units < threshold |
| 8 | `Average Dollar Sales per Warehouse Selling` | Dollar Sales ÷ number of warehouses selling | No |
| 9 | `Average Unit Sales per Warehouse Selling` | Unit Sales ÷ number of warehouses selling | No |
| 10 | `Item Description` | Costco's description for the product selected (blank for brand aggregate) | No |
| 11 | `Item Number` | Costco's item code for the product selected (blank for brand aggregate) | No |
| 12 | `UPC` | Manufacturer's UPC code (blank for brand aggregate) | No |
| 13 | `Average Coupon Value` | Discount amount for a particular item; only populates when there is an active coupon | Informational only |
| 14 | `Average Promoted Price` | Price of an item after the coupon has been applied | Informational only |
| 15 | `% Discount` | Percentage of the regular price saved by using a coupon (**on promoted units only** — NOT blended) | ⚠️ **Do NOT use directly** (see Section 4.5) |
| 16 | `Non Promoted Dollars` | Dollar Sales (net of returns) when no promotion was present | **Yes** — for Base Price calculation (primary) |
| 17 | `Non Promoted Units` | Unit Sales (net of returns) when no promotion was present | **Yes** — for Base Price calculation (primary) |
| 18 | `Net Dollars` | Promoted Dollars (+) Non Promoted Dollars | **Yes** — for Avg Net Price / promo depth |
| 19 | `Promoted Dollars` | Dollar Sales due to promotion, net of coupons and returns | Informational only |
| 20 | `Promoted Units` | Unit Sales due to promotion, net of coupons and returns | Informational only |
| 21 | `Total Discount Dollars` | Total sales discount applied to item as result of promotion | Informational only |
| 22 | `Avg Net Price` | Dollar Sales (−) Promotion Dollars (−) Total Discount Dollars, divided by Unit Sales | **Yes** — maps to Avg Price Paid |
| 23 | `OOS %` | Out-of-stock percentage between OOS and In-Stock locations | No (potential future enhancement) |

### 2.3 Columns in Data Dictionary but MISSING from CSV

The Costco CRX Measure Guide defines the following measures that are **not present in the current data extract**. If provided in a future extract, they would strengthen the analysis:

| Missing Column | Data Dictionary Definition | How It Would Be Used | Priority |
|---|---|---|---|
| `Gross Dollars` | All Dollar Sales including Discounts and Returns | Would provide true gross revenue before any adjustments; enables direct `Avg_Price_SI = (Gross Dollars − Coupon Dollars) / Gross Units` | 🟡 Medium — currently handled via `Avg Net Price` |
| `Gross Units` | All Unit Sales including Discounts and Returns | Would provide true gross units before returns; needed alongside `Gross Dollars` for alternative avg price calculation | 🟡 Medium — currently handled via `Unit Sales` (which is net of returns) |
| `Coupon Dollars` | Total Dollars for Coupons Redeemed | Would enable direct coupon-adjusted price calculation and validate `Total Discount Dollars` | 🟡 Medium — `Total Discount Dollars` serves a similar role |
| `Coupon Units` | Total Units sold with a coupon | Would confirm exact promo penetration rates per week; useful for promo intensity analysis | 🟢 Low — `Promoted Units` serves a similar role |
| `Refunded Dollars` | Dollar amount refunded | Would clarify the returns adjustment embedded in `Dollar Sales` and `Non Promoted Dollars` | 🟢 Low — returns appear minimal in current data |
| `Refunded Units` | Number of Units returned | Would clarify the returns adjustment embedded in `Unit Sales` and `Non Promoted Units` | 🟢 Low — returns appear minimal in current data |

**Note:** The current CSV provides sufficient data for the elasticity model. These missing columns would primarily add **validation redundancy** and enable an **alternative average price calculation path**. They are not blockers for the Costco integration.

---

## 3. Product Filtering: Brand-Level Aggregate

### 3.1 BJ's/Sam's approach
Filter `Product` column to rows containing `"SPARKLING ICE"` for Sparkling Ice data, and rows containing `"PRIVATE LABEL"` for Private Label/cross-price data.

Exact values:
- `SPARKLING ICE BASE-BOTTLED WATER-SELTZER/SPARKLING/MINERAL WATER` (159 rows)
- `PRIVATE LABEL-BOTTLED WATER-SELTZER/SPARKLING/MINERAL WATER` (318 rows)

### 3.2 Costco approach
Filter `Item` column to the **brand-level aggregate row only**:
- `Sparkling Ice Core 17oz 24ct 2023 through 2025 Items` (161 rows)

**Discard the 11 individual UPC rows.** These are:

| Item | Description |
|---|---|
| ITEM 001422384 | SPARKLING ICE FRUIT BLST VTY PK 17 OZ /24CT P60 |
| ITEM 001692514 | SPARKLING ICE 24/17 OZ FALL VARIETY P=60 |
| ITEM 001730948 | SPARKLING ICE 24/17 OZ SUMMER LEMONADE VTY P60 |
| ITEM 001733666 | SPARKLING ICE 24/17 OZ WINTER VARIETY P=60 |
| ITEM 001810158 | SPARKLING ICE CLASSICS VRTY PACK 24/17OZ |
| ITEM 001815042 | SPARKLING ICE 24/17 OZ ZERO SUGAR 12X5 P60 |
| ITEM 001815076 | SPARKLING ICE LEMONADE 24/17 OZ ZERO SUGAR P60 |
| ITEM 001867505 | SPARKLING ICE 24/17OZ HOLIDAY 12X5 P60 |
| ITEM 001887142 | SPARKLING ICE STARBURST 24/17OZ VTY T12H5 P60 |
| ITEM 001953679 | SPARKLING ICE HOLIDAY CELEBRATION PACK 12X5 P60 |
| ITEM 001984658 | SPARKLING ICE STARBURST 24/17Z T12H5P60 |

**Verified:** Brand aggregate `Dollar Sales` = exact sum of all 11 UPC `Dollar Sales` for any given week. Same for `Unit Sales`. The aggregate is a true roll-up.

### 3.3 Private Label
No Private Label data exists in the Costco CRX file. The cross-price term will be zeroed out via `has_competitor = 0`.

---

## 4. Column-by-Column Transformation Mapping

### 4.1 Overview: Costco → Model-Ready Fields

| Model-Ready Field | Description | BJ's/Sam's Calculation | Costco Calculation | Status |
|---|---|---|---|---|
| `Retailer` | Identifier for the retail channel (BJs, Sams, Costco) | Derived from file / geography row | Hardcode `"Costco"` | ✅ Agreed |
| `Date` | Week-ending date, weekly grain | Parse `Time`: `"Week Ending 01-08-23"` | Parse `Time`: `"1 week ending 01-08-2023"` | ✅ Different format, same grain |
| `Volume_Sales_SI` | Sparkling Ice sales volume in Circana standardized volume units (1 unit = 204 oz) — the dependent variable (Y) | Direct: `Volume Sales` column | Computed: `Unit Sales × 2.0` | ✅ See Section 4.2 |
| `Base_Price_SI` | Everyday/regular price per unit absent promotional activity — the strategic price lever | `Base Dollar Sales / Base Unit Sales` | `Non Promoted Dollars / Non Promoted Units` (fallback: `Average Price per Unit`) | ✅ See Section 4.3 |
| `Avg_Price_SI` | Average price actually paid by consumers (blended across promoted and non-promoted units) | `Dollar Sales / Unit Sales` | `Avg Net Price` | ⚠️ See Section 4.4 — critical difference. **Alert:** `Gross Dollars` and `Coupon Dollars` columns (defined in data dictionary but missing from CSV) would enable an alternative calculation: `(Gross Dollars − Coupon Dollars) / Gross Units`. See Section 2.3. |
| `Promo_Depth_SI` | Percentage discount relative to base price; 0 = no discount, −0.10 = 10% off — the tactical promo lever | `(Avg_Price_SI / Base_Price_SI) − 1` | `(Avg Net Price / NP Base Price) − 1` | ✅ See Section 4.5 |
| `Price_PL` | Private Label average price per unit — cross-price competitive control | `Dollar Sales_PL / Unit Sales_PL` | **Not available** | ❌ `has_competitor = 0` |
| `Log_Volume_Sales_SI` | Natural log of Volume_Sales_SI — model dependent variable | `ln(Volume_Sales_SI)` | `ln(Unit Sales × 2.0)` | ✅ |
| `Log_Base_Price_SI` | Natural log of Base_Price_SI — coefficient is the base price elasticity (β₁) | `ln(Base_Price_SI)` | `ln(Non Promoted Dollars / Non Promoted Units)` | ✅ |
| `Log_Price_PL` | Natural log of Price_PL — coefficient is the cross-price elasticity (β₃) | `ln(Price_PL)` | Set to `0.0` (masked out) | ✅ |
| `Spring` | Seasonal dummy: 1 if Mar–May, else 0 | From date month (Mar–May) | Same logic | ✅ |
| `Summer` | Seasonal dummy: 1 if Jun–Aug, else 0 | From date month (Jun–Aug) | Same logic | ✅ |
| `Fall` | Seasonal dummy: 1 if Sep–Nov, else 0 | From date month (Sep–Nov) | Same logic | ✅ |
| `Week_Number` | Linear time trend: weeks since first observation in dataset | `(Date − min(Date)).days / 7` | Same logic | ✅ |
| `has_promo` | Retailer-level mask: 1 if promo depth is computable for this retailer, else 0 | `1` | `1` | ✅ Costco HAS promo data |
| `has_competitor` | Retailer-level mask: 1 if Private Label price data exists for this retailer, else 0 | `1` | `0` | ✅ Costco has NO PL data |

### 4.2 Volume Sales: `Unit Sales × 2.0`

Costco's CRX data does not include a `Volume Sales` column. All Sparkling Ice items at Costco are **24-pack / 17 oz** (408 oz per case).

In BJ's/Sam's Circana data, 1 volume unit = 204 oz (a 12-pack equivalent). The observed ratio is exactly `Volume Sales = Unit Sales × 2.0` across all weeks (correlation = 1.0000), because the dominant pack size is 24-packs.

**Transformation:** `Volume_Sales_SI = Unit Sales × 2.0`

This is consistent with the existing `PrepConfig.volume_sales_factor_by_retailer` fallback mechanism already documented in the contract.

**Important note for elasticity:** Because the log transformation absorbs the constant factor (`ln(Units × 2) = ln(Units) + ln(2)`), the elasticity coefficients β₁ and β₂ are **identical** whether we use Volume Sales or Unit Sales. Only the intercept β₀ changes by +0.693. The multiplication is for consistency with BJ's/Sam's units.

### 4.3 Base Price: `Non Promoted Dollars / Non Promoted Units`

**This is the most important conceptual mapping.**

#### Understanding Circana's Base Sales (BJ's/Sam's)

Circana's `Base Dollar Sales` and `Base Unit Sales` are **modeled estimates** — statistical projections of what sales would have been *absent all promotional activity*:

- **Base Dollar Sales:** Estimated dollar sales that would have occurred without any merchandising support (no price reduction, no feature, no display). In plain English: "What consumers would have bought at regular price, absent promotions."
- **Base Unit Sales:** Estimated number of units sold without merchandising effects. Conceptually: `Base Unit Sales = Observed Unit Sales − Incremental Unit Sales`.
- **What's removed:** Temporary price reductions (TPR), feature ads, in-store displays, and any combination of the above.

Therefore, the BJ's/Sam's base price is:
```
Base_Price_SI = Base Dollar Sales / Base Unit Sales
             = Circana's modeled regular price (what consumers would have paid without promos)
```

#### Costco's Equivalent: Non Promoted Dollars / Non Promoted Units

Costco's CRX data does not have Circana's modeled base sales decomposition. However, it has `Non Promoted Dollars` and `Non Promoted Units` — the **actual sales that occurred without any coupon/promotion**. These represent units sold at the regular shelf price with no discount applied.

This is the closest conceptual equivalent to Circana's base sales: Circana *estimates* what would have sold at regular price; Costco's NP fields *observe* what actually did sell at regular price.

**Primary formula:**
```
Base_Price_SI = Non Promoted Dollars / Non Promoted Units
```

#### Data Validation

| Metric | Value |
|---|---|
| Weeks with `Non Promoted Units` ≤ 0 | **0 of 161** (no division-by-zero risk) |
| Weeks with `Non Promoted Units` < 500 | **3 of 161** (heavy promo weeks) |
| Minimum `Non Promoted Units` in any week | 487 (week of 02-11-2024, 0.3% of total) |
| NP Price mean | $16.19 (±$0.60) |
| Shelf Price (`Average Price per Unit`) mean | $16.20 (±$0.59) |
| Max deviation between NP Price and Shelf Price | $0.19 (week of 02-09-2025) |

Even in the heaviest promo weeks (where 99.7% of units are on coupon), the NP price remains stable in the $15.83–$16.18 range — well within normal price variation.

#### Fallback Strategy (for future data stability)

If future data refreshes show instability in the NP ratio (e.g., `Non Promoted Units` dropping to near-zero or the NP price spiking unrealistically), the fallback hierarchy is:

1. **Primary:** `Non Promoted Dollars / Non Promoted Units` — closest to Circana's base price concept
2. **Fallback Level 1:** `Average Price per Unit` — the shelf/list price, pre-computed, always available, stable every week, and within $0.05–$0.19 of the NP price even in worst cases
3. **Fallback Level 2:** Rolling median of NP price from non-promo weeks (where NP units are large and the ratio is most reliable), forward-filled into promo weeks

**Implementation rule:** If `Non Promoted Units` < threshold (recommended: 500 units or 1% of total `Unit Sales` for that week), substitute `Average Price per Unit` for that week.

**Current data status:** All 161 weeks have `Non Promoted Units` ≥ 487. The primary formula is stable and no fallback is currently needed.

### 4.4 Average Price Paid: `Avg Net Price` (CRITICAL DIFFERENCE)

**⚠️ This is where Costco's data model fundamentally differs from BJ's/Sam's.**

**Data dictionary confirmation:** The CRX Measure Guide confirms the key definitions:
- `Dollar Sales` = "Gross Dollar Sales net of Returns" — net of returns but **still includes sales at shelf price** (pre-coupon)
- `Average Price per Unit` = "Regular price of an item — will reflect any competitive price match" — this is the **shelf/list price**
- `Avg Net Price` = "Dollar Sales (−) Promotion Dollars (−) Total Discount Dollars" — the **actual net price** after all discounts

This confirms that `Dollar Sales / Unit Sales` gives the shelf price, NOT the price consumers actually paid.

In BJ's/Sam's (Circana):
```
Avg_Price_SI = Dollar Sales / Unit Sales
```
Here, `Dollar Sales` reflects **actual transaction revenue** — it already incorporates any discounts. When a promo week has 10% off, `Dollar Sales` is lower, so the calculated average price is lower.

In Costco (CRX):
```
Dollar Sales / Unit Sales ≈ Average Price per Unit ≈ $16.02 (the SHELF price)
```
Costco's `Dollar Sales` represents **gross sales at shelf/list price** (net of returns but NOT net of coupons). Evidence:

| Week (promo) | Dollar Sales / Unit Sales | Avg Net Price | Interpretation |
|---|---|---|---|
| 02-05-2023 | $16.01 | $12.06 | Dollar Sales is at shelf price |
| 02-12-2023 | $16.01 | $11.73 | Avg Net Price reflects actual price paid |

The correct "average price paid" for Costco is the **`Avg Net Price`** column, which is:
```
Avg Net Price = Net Dollars / Unit Sales
```
where:
```
Net Dollars = Dollar Sales − Total Discount Dollars
```

**Verified relationship:**
```
Net Dollars = Non Promoted Dollars + Promoted Dollars  ✅ (exact match)
Avg Net Price = Net Dollars / Unit Sales               ✅ (exact match)
```

**Transformation:** `Avg_Price_SI = Avg Net Price`

**DO NOT USE:** `Dollar Sales / Unit Sales` for Costco — this gives the shelf price, not the actual price paid, and would result in promo depth ≈ 0 for every week.

**Alternative calculation (if missing columns become available):** The data dictionary defines `Gross Dollars` ("All Dollar Sales including Discounts and Returns") and `Coupon Dollars` ("Total Dollars for Coupons Redeemed"), which are not in the current CSV. If provided in a future extract, these would enable a direct calculation: `Avg_Price_SI = (Gross Dollars − Coupon Dollars) / Gross Units`, which should equal `Avg Net Price`. See Section 2.3 for the full list of missing columns.

### 4.5 Promo Depth: `(Avg Net Price / NP Base Price) − 1`

With the base price and average price mapped, the promo depth calculation follows the same formula as BJ's/Sam's:

```
Promo_Depth_SI = (Avg_Price_SI / Base_Price_SI) − 1
               = (Avg Net Price / (Non Promoted Dollars / Non Promoted Units)) − 1
```

**Validation across week types:**

| Week Type | Avg Net Price | NP Base Price | Promo Depth | Interpretation |
|---|---|---|---|---|
| Non-promo (01-01-2023) | $16.021 | $16.020 | +0.00002 (≈ 0) | ✅ No discount |
| Heavy promo (02-05-2023) | $12.064 | $16.017 | −0.247 (−24.7%) | ✅ Deep discount |
| Light promo (05-28-2023) | $15.914 | $16.027 | −0.007 (−0.7%) | ✅ Small blended discount (only 3.2% of units on promo) |

**⚠️ Do NOT use the `% Discount` column directly.** This column reports the coupon discount rate on **promoted units only** (e.g., 26.7%), not the blended discount across all units. In weeks where only 3% of units are promoted, `% Discount` = 21.8% but the actual blended promo depth is only −0.7%. The `(Avg Net Price / NP Base Price) − 1` formula correctly captures the blended, volume-weighted discount, which is conceptually identical to what BJ's/Sam's promo depth measures.

### 4.6 Date Parsing

| Retailer | Raw Format | Example | Parse Logic |
|---|---|---|---|
| BJ's/Sam's | `Week Ending MM-DD-YY` | `Week Ending 01-08-23` | Strip prefix, parse `%m-%d-%y` |
| Costco | `N week ending MM-DD-YYYY` | `1 week ending 01-08-2023` | Strip prefix through "ending ", parse `%m-%d-%Y` |

Both represent the same weekly grain (week-ending Sunday/Saturday dates). The date ranges overlap substantially (Jan 2023 – Jan 2026).

### 4.7 Availability Masks

| Mask | BJ's | Sam's | Costco | Rationale |
|---|---|---|---|---|
| `has_promo` | 1 | 1 | **1** | Costco has `Non Promoted Dollars/Units` and `Avg Net Price` → promo depth is computable |
| `has_competitor` | 1 | 1 | **0** | No Private Label data in Costco CRX file |

With `has_competitor = 0`, the cross-price term `β₃ · Log_Price_PL` is multiplied by zero for all Costco rows. Costco still contributes to estimating base price elasticity (β₁), promotional elasticity (β₂), seasonality, and time trend.

In the hierarchical model, Costco's cross-price elasticity (β₃) will be pulled toward the global mean learned from BJ's and Sam's via partial pooling — it gets a "borrowed" estimate rather than no estimate.

---

## 5. Promotional Data: Deep Dive

Costco's CRX system provides richer explicit promo fields than Circana. While we only use three fields for the core model (`Non Promoted Dollars`, `Non Promoted Units`, and `Avg Net Price`), the remaining fields are valuable for validation and future enhancements.

### 5.1 How Costco Promotions Work (Coupon-Based)

Costco promotions are primarily **coupon/instant-rebate-based**, not shelf-price reductions:
- The shelf price stays constant (e.g., $16.02)
- A coupon reduces the effective price for the consumer (e.g., $4.28 off → $11.73 effective)
- Not all units in a promo week are sold on promotion

**Key relationship (verified):**
```
Average Promoted Price = Average Price per Unit − Average Coupon Value
Example: $11.73 = $16.02 − $4.28  ✅ (exact match)
```

### 5.2 Dollar Decomposition (verified)

```
Dollar Sales          = Gross revenue at shelf price (before coupons)
Total Discount Dollars = Total coupon/rebate dollars given
Net Dollars           = Dollar Sales − Total Discount Dollars  ✅

Net Dollars           = Non Promoted Dollars + Promoted Dollars  ✅
Unit Sales            = Non Promoted Units + Promoted Units       ✅
```

**Important:** `Promoted Dollars` represents the net revenue from promoted units (after discounts), NOT the gross revenue from those units.

### 5.3 Non-Promo Week Behavior

In weeks with no active coupon (`Average Coupon Value` = NaN):
- `Non Promoted Units ≈ Unit Sales` (all units sold at regular price)
- `Promoted Dollars` and `Promoted Units` are near-zero or slightly negative (rounding artifacts)
- `Avg Net Price ≈ Average Price per Unit` (difference < $0.01)
- `Promo Depth ≈ 0.0000` ✅

**Distribution:** 102 of 161 weeks (63%) are non-promo weeks; 59 weeks (37%) have active coupons.

### 5.4 Fields NOT Used (and why)

| Field | Why Not Used (or role) |
|---|---|
| `% Discount` | Measures coupon rate on promoted units only, not blended depth. Misleading when promo penetration is low. |
| `Average Coupon Value` | Per-unit coupon amount — useful for understanding promo mechanics but not needed when we compute blended depth from net vs base price. |
| `Average Promoted Price` | Price for promoted units only — not the blended price we need for the model. |
| `Average Price per Unit` | Shelf/list price. Used as **fallback** for `Base_Price_SI` when `Non Promoted Units` < threshold. Not the primary choice because it's a list price, not observed regular-price transactions. |
| `Promoted Dollars / Promoted Units` | Useful for trade spend analysis but not needed for the elasticity model. |
| `OOS %` | Out-of-stock data could be a valuable future enhancement. |

---

## 6. Final Model-Ready Output Schema

After transformation, a Costco row in the model-ready DataFrame is identical in structure to a BJ's or Sam's row:

```
Date       | Retailer | Log_Volume_Sales_SI | Log_Base_Price_SI | Promo_Depth_SI | Log_Price_PL | Spring | Summer | Fall | Week_Number | has_promo | has_competitor
-----------|----------|---------------------|-------------------|----------------|--------------|--------|--------|------|-------------|-----------|---------------
2023-01-08 | BJs      | 10.07               | 2.91              | -0.025         | 0.59         | 0      | 0      | 0    | 0           | 1         | 1
2023-01-08 | Sams     | 11.80               | 2.77              | -0.014         | 0.62         | 0      | 0      | 0    | 0           | 1         | 1
2023-01-08 | Costco   | 11.37               | 2.77              |  0.000         | 0.00         | 0      | 0      | 0    | 0           | 1         | 0
```

The hierarchical model then runs on the combined DataFrame with retailer-level random effects for β₁ (base elasticity), β₂ (promo elasticity), and optionally β₃ (cross-price, informed only by BJ's/Sam's due to masking).

---

## 7. Transformation Summary (Pseudocode)

```python
# === COSTCO DATA TRANSFORMATION ===

# Step 1: Load
costco_raw = pd.read_csv('costco.csv', skiprows=1)

# Step 2: Filter to brand-level aggregate
costco = costco_raw[
    costco_raw['Item'] == 'Sparkling Ice Core 17oz 24ct 2023 through 2025 Items'
].copy()

# Step 3: Parse date
# "1 week ending 01-08-2023" → extract date portion after "ending "
costco['Date'] = costco['Time'].str.extract(r'ending (\d{2}-\d{2}-\d{4})')[0]
costco['Date'] = pd.to_datetime(costco['Date'], format='%m-%d-%Y')

# Step 4: Assign retailer
costco['Retailer'] = 'Costco'

# Step 5: Volume Sales (no column exists → compute)
costco['Volume_Sales_SI'] = costco['Unit Sales'] * 2.0

# Step 6: Base Price (Non Promoted price — closest to Circana's base price concept)
# Primary: NP Dollars / NP Units (actual regular-price transactions)
# Fallback: Average Price per Unit (shelf/list price) when NP Units < threshold
NP_UNITS_THRESHOLD = 500  # or 1% of Unit Sales
costco['Base_Price_SI'] = np.where(
    costco['Non Promoted Units'] >= NP_UNITS_THRESHOLD,
    costco['Non Promoted Dollars'] / costco['Non Promoted Units'],  # Primary
    costco['Average Price per Unit']                                 # Fallback
)

# Step 7: Average Price Paid (net of discounts)
# CRITICAL: Use Avg Net Price, NOT Dollar Sales / Unit Sales
costco['Avg_Price_SI'] = costco['Avg Net Price']

# Step 8: Promo Depth (same formula as BJ's/Sam's)
costco['Promo_Depth_SI'] = (costco['Avg_Price_SI'] / costco['Base_Price_SI']) - 1

# Step 9: Private Label (not available)
costco['Price_PL'] = np.nan  # will be masked out

# Step 10: Log transformations
costco['Log_Volume_Sales_SI'] = np.log(costco['Volume_Sales_SI'])
costco['Log_Base_Price_SI'] = np.log(costco['Base_Price_SI'])
costco['Log_Price_PL'] = 0.0  # masked out by has_competitor

# Step 11: Seasonality dummies (from Date)
costco['month'] = costco['Date'].dt.month
costco['Spring'] = costco['month'].isin([3, 4, 5]).astype(int)
costco['Summer'] = costco['month'].isin([6, 7, 8]).astype(int)
costco['Fall']   = costco['month'].isin([9, 10, 11]).astype(int)

# Step 12: Time trend
min_date = costco['Date'].min()  # or global min across all retailers
costco['Week_Number'] = ((costco['Date'] - min_date).dt.days / 7).astype(int)

# Step 13: Availability masks
costco['has_promo'] = 1       # Costco HAS promo data
costco['has_competitor'] = 0  # Costco has NO Private Label data

# Step 14: Select model-ready columns and append to BJ's/Sam's DataFrame
```

---

## 8. Validation Checks (Post-Transformation)

These checks should pass before the combined DataFrame enters the model:

| Check | Expected | How to Verify |
|---|---|---|
| Costco row count | ~161 weeks | `df[df.Retailer == 'Costco'].shape[0]` |
| `Volume_Sales_SI` > 0 | All rows | No zeros or negatives |
| `Base_Price_SI` range | $15.50 – $18.50 | Consistent with 24-pack shelf pricing |
| `Promo_Depth_SI` range | −0.30 to +0.001 | Non-promo weeks ≈ 0; promo weeks negative |
| Non-promo weeks Promo_Depth ≈ 0 | |Depth| < 0.001 for non-coupon weeks | Verify against `Average Coupon Value` being NaN |
| `has_promo` = 1 for all Costco rows | 161 rows | Constant |
| `has_competitor` = 0 for all Costco rows | 161 rows | Constant |
| `Log_Price_PL` = 0 for all Costco rows | 161 rows | Masked out |
| Date overlap with BJ's/Sam's | Jan 2023 – Jan 2026 | Comparable time windows |
| No duplicate Date-Retailer combinations | 0 duplicates | `df.duplicated(subset=['Date','Retailer'])` |

---

## 9. Impact on the Hierarchical Model

### 9.1 What Costco Contributes

With `has_promo = 1` and `has_competitor = 0`, Costco will contribute to estimating:

- ✅ **β₁ (Base Price Elasticity)** — Costco has strong base price variation across 161 weeks
- ✅ **β₂ (Promotional Elasticity)** — Costco has 59 promo weeks with meaningful depth variation (up to −25%)
- ✅ **β₄–β₆ (Seasonality)** — Full seasonal coverage
- ✅ **β₇ (Time Trend)** — 3-year time series
- ❌ **β₃ (Cross-Price Elasticity)** — Zeroed out; Costco borrows from BJ's/Sam's via partial pooling

### 9.2 Expected Hierarchical Structure (3 retailers)

```
Level 1 (Global):
  μ_base_global  ~ Normal(-2.0, 0.5)
  μ_promo_global ~ Normal(-4.0, 1.0)
  σ_base_group   ~ HalfNormal(0.3)
  σ_promo_group  ~ HalfNormal(0.5)

Level 2 (Retailer-specific):
  base_elasticity_BJs    ~ Normal(μ_base_global, σ_base_group)
  base_elasticity_Sams   ~ Normal(μ_base_global, σ_base_group)
  base_elasticity_Costco ~ Normal(μ_base_global, σ_base_group)  ← NEW

  promo_elasticity_BJs    ~ Normal(μ_promo_global, σ_promo_group)
  promo_elasticity_Sams   ~ Normal(μ_promo_global, σ_promo_group)
  promo_elasticity_Costco ~ Normal(μ_promo_global, σ_promo_group)  ← NEW

Level 3 (Observation): Same equation for all retailers
```

Adding Costco as a third retailer strengthens the hierarchical model by providing an additional signal for the global mean and between-retailer variance parameters. The model can now answer: "How much do elasticities vary across three distinct club retailers?"

---

## 10. Open Items and Future Enhancements

| Item | Status | Notes |
|---|---|---|
| Base Price mapping | **✅ Agreed** | Primary: `Non Promoted Dollars / Non Promoted Units`; Fallback: `Average Price per Unit` |
| Circana Base Sales definition | **✅ Confirmed** | Circana Base Dollar/Unit Sales are modeled estimates of demand absent all promotional activity |
| Confirm `Dollar Sales` is at shelf price (pre-coupon) | **Pending confirmation from Atul** | Evidence is strong (Section 4.4) but formal confirmation needed |
| Costco data dictionary (XLS file) | Available but unreadable without `xlrd` library | Should be reviewed to confirm field definitions |
| `OOS %` (Out-of-Stock) | Not used | Could be a future control variable — stock-outs depress sales independently of price |
| UPC-level modeling | Not used | 11 UPCs available if SKU-level analysis is needed in the future |
| Costco Private Label | Not available | If obtainable from another source, would enable cross-price analysis at Costco |
| `Warehouses Selling` | Not used | Could normalize volume on a per-warehouse basis for distribution-adjusted elasticity |

---

## 11. Document History

| Version | Date | Change |
|---|---|---|
| 1.0 | February 5, 2026 | Initial contract — complete mapping from Costco CRX to model-ready format |
| 1.1 | February 5, 2026 | **Base Price updated**: changed from `Average Price per Unit` to `Non Promoted Dollars / Non Promoted Units` (with fallback) based on alignment with Circana's modeled base sales concept. Added Circana Base Dollar/Unit Sales definitions. Added data validation and fallback strategy. |
| 1.2 | February 5, 2026 | **Data dictionary integration**: Added Section 2.3 (columns defined in CRX Measure Guide but missing from CSV). Enriched Section 2.2 with official data dictionary definitions for all 23 columns. Added data dictionary confirmations to Section 4.4. Added alternative `Avg_Price_SI` calculation path via `Gross Dollars`/`Coupon Dollars` if those columns become available. Added alert note to Table 4.1. |

---

**Status:** 🟡 DRAFT — Base Price mapping agreed (v1.1). Continuing alignment on remaining fields.

**Next Step:** Once this mapping is agreed upon, modify `data_prep.py` to add a Costco transformation path and run the 3-retailer hierarchical model.
