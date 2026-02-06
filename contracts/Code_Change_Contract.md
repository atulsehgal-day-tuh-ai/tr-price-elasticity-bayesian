# Code Change Contract: Config-Driven Retailer Support
## data_prep.py v2.1 + config_template.yaml v2.0

**Prepared for:** Atul Sehgal  
**Date:** February 5, 2026  
**Purpose:** Document every code change made to `data_prep.py` and `config_template.yaml` to support Costco as a third retailer, with zero hardcoded retailer logic.

---

## 1. Design Principle

**No `if retailer == 'Costco'` anywhere in the code.**

Every retailer-specific behavior — column names, date formats, price calculations, fallback rules — is driven by a `retailer_data_contracts` section in the YAML config. Adding a 4th retailer in the future requires only a new YAML block and zero code changes.

---

## 2. What Changed in `config_template.yaml`

### 2.1 New Section: `retailer_data_contracts`

This is the core addition. Each retailer gets a contract block that specifies:

| Field | Purpose | Example (Costco) |
|---|---|---|
| `skiprows` | Header rows to skip when reading CSV | `1` (vs `2` for Circana) |
| `product_column` | Column name containing product identifiers | `"Item"` (vs `"Product"` for Circana) |
| `brand_filter` | Lowercase substring for fuzzy-matching Sparkling Ice | `"sparkling ice core"` |
| `competitor_filter` | Lowercase substring for Private Label (null if none) | `null` |
| `date_column` | Column containing date/time | `"Time"` |
| `date_prefix` | (Option A) Prefix to strip before parsing | Used by BJ's/Sam's: `"Week Ending "` |
| `date_regex` | (Option B) Regex with capture group to extract date | Used by Costco: `"ending (\\d{2}-\\d{2}-\\d{4})"` |
| `date_format` | strftime format for the date string | `"%m-%d-%Y"` (4-digit year for Costco) |
| `price_calc.avg_price` | Formula or column name for average price paid | `"Avg Net Price"` (direct column) |
| `price_calc.base_price` | Formula or column name for base/regular price | `"Non Promoted Dollars / Non Promoted Units"` |
| `price_calc.base_price_fallback` | Fallback column when primary is unreliable | `"Average Price per Unit"` |
| `price_calc.base_price_min_units` | Threshold below which fallback is triggered | `500` |
| `volume_column` | Direct volume column (null if needs computation) | `null` (uses `volume_sales_factor_by_retailer`) |

### 2.2 Updated: `retailers` Section

Changed Costco from commented-out to active:

```yaml
# Before:
# Costco:
#   has_promo: false
#   has_competitor: true

# After:
Costco:
  has_promo: true          # Costco HAS promotional data
  has_competitor: false     # Costco has NO Private Label data
```

### 2.3 Updated: `costco_path`

Changed from `null` to `"data/costco.csv"` as Costco is now a supported retailer.

---

## 3. What Changed in `data_prep.py`

### 3.1 New: `PrepConfig.retailer_data_contracts` Field

```python
retailer_data_contracts: Optional[Dict] = None
```

Added to the dataclass so the YAML contracts are available to all methods.

### 3.2 New: Contract Helper Methods

| Method | Purpose |
|---|---|
| `_get_contract(retailer)` | Looks up the data contract for a retailer by exact or normalized name match |
| `_norm_retailer(s)` | Normalizes retailer strings (lowercases, strips punctuation) for robust matching. Promoted from local function to static method for reuse. |

### 3.3 Changed: `_load_data()` → `_load_single_retailer()` + `_load_data()`

**Before:** Each retailer was loaded with hardcoded `skiprows=2` and no column renaming.

**After:** `_load_single_retailer()` reads the contract to determine:
- `skiprows` (1 for Costco, 2 for Circana)
- `product_column` rename (Costco's `Item` → `Product` for downstream compatibility)

`_load_data()` now calls `_load_single_retailer()` for each retailer.

**Why:** Costco's CSV has 1 header row (not 2) and uses `Item` instead of `Product`. Without this change, the Costco CSV would be parsed with wrong column headers.

### 3.4 Changed: `_clean_data()` — Date Parsing

**Before:**
```python
df['Date'] = pd.to_datetime(
    df['Time'].str.replace('Week Ending ', ''),
    format='%m-%d-%y'
)
```
Hardcoded Circana date format.

**After:** Delegates to `_parse_date_for_retailer()` which reads the contract to determine:
- `date_regex` (Costco: extract from `"1 week ending 01-08-2023"`)
- `date_prefix` (BJ's/Sam's: strip `"Week Ending "`)
- `date_format` (`%m-%d-%Y` for Costco's 4-digit year, `%m-%d-%y` for Circana's 2-digit)

Dates are parsed **per retailer** in a loop, then concatenated back.

**Why:** Costco uses `"1 week ending 01-08-2023"` (regex extraction needed) vs Circana's `"Week Ending 01-08-23"` (prefix stripping). A single hardcoded parser would fail on one format or the other.

### 3.5 Changed: `_clean_data()` — Average Price Calculation

**Before:**
```python
df['Avg_Price'] = df['Dollar Sales'] / df['Unit Sales']
```
Applied uniformly to all retailers.

**After:** Delegates to `_compute_avg_price_for_retailer()` which reads `price_calc.avg_price` from the contract:
- BJ's/Sam's: `"Dollar Sales / Unit Sales"` → division formula (same as before)
- Costco: `"Avg Net Price"` → direct column reference

**Why:** This is the **most critical change**. Costco's `Dollar Sales / Unit Sales` gives the shelf/list price (~$16), NOT the price consumers actually paid. The net price after coupons (~$12 during promos) is in `Avg Net Price`. Using the wrong column would make promo depth ≈ 0 for every week, destroying the promotional elasticity signal.

### 3.6 New: `_compute_base_price_for_retailer()`

**Before:** Base price was computed from `Base Dollar Sales / Base Unit Sales` in `_clean_data()`, then refined in `_add_base_and_promo_depth()`.

**After:** New method reads `price_calc.base_price` from the contract:
- BJ's/Sam's: `"Base Dollar Sales / Base Unit Sales"` (Circana's modeled base decomposition)
- Costco: `"Non Promoted Dollars / Non Promoted Units"` (actual non-promoted transactions)

Also supports:
- `base_price_fallback`: Column to use when primary is unreliable (Costco: `"Average Price per Unit"`)
- `base_price_min_units`: Threshold that triggers fallback (Costco: 500 units)

The fallback logic: if `Non Promoted Units < 500` for a given row, substitute `Average Price per Unit` (the shelf price) instead.

**Why:** Costco has no Circana-style base sales decomposition. `Non Promoted Dollars / Non Promoted Units` is the closest conceptual equivalent (see Costco Data Integration Contract v1.2, Section 4.3). The fallback handles edge cases where heavy promo weeks have very few non-promoted units.

### 3.7 Changed: `_clean_data()` — Product Filtering

**Before:** Exact match against `brand_filters` list, then fuzzy fallback using hardcoded substrings `'sparkling ice'` and `'private label'`.

**After:** Two-layer approach:
1. Exact match against `brand_filters` (unchanged — still works for BJ's/Sam's)
2. Fuzzy fallback now reads `brand_filter` and `competitor_filter` **per retailer** from the contract

For Costco, `brand_filter: "sparkling ice core"` ensures only the brand-level aggregate row matches (not the 11 individual UPC rows which also contain "sparkling ice" but NOT "core").

**Why:** Costco has 12 rows per week (1 aggregate + 11 UPCs), all containing "sparkling ice" in the name. Using `"sparkling ice"` alone would match all 12, causing 11× data duplication. The more specific `"sparkling ice core"` uniquely identifies the aggregate.

### 3.8 Changed: `_pivot_to_wide()` — Private Label Handling

**Before:** Assumed `Private Label_sales` and `Private Label_price` columns would always exist after pivot.

**After:** Checks for existence before renaming:
```python
if 'Private Label_sales' in wide.columns:
    rename_map['Private Label_sales'] = 'Volume_Sales_PL'
if 'Private Label_price' in wide.columns:
    rename_map['Private Label_price'] = 'Price_PL'
```

**Why:** Costco has no Private Label data. Without this guard, the pivot would create columns with all NaN values, and the rename would still work, but the downstream `np.log(df['Price_PL'])` would produce all NaN → all rows dropped. Now, when `Price_PL` doesn't exist, `Log_Price_PL` is set to `0.0` (masked out by `has_competitor = 0`).

### 3.9 Changed: `_create_features()` — Log_Price_PL Robustness

**Before:**
```python
df_wide['Log_Price_PL'] = np.log(df_wide['Price_PL'])
```
Would fail or produce NaN if `Price_PL` is missing.

**After:**
```python
if 'Price_PL' in df_wide.columns:
    df_wide['Log_Price_PL'] = np.where(
        df_wide['Price_PL'].notna() & (df_wide['Price_PL'] > 0),
        np.log(df_wide['Price_PL']),
        0.0
    )
else:
    df_wide['Log_Price_PL'] = 0.0
```

**Why:** For retailers without Private Label data (Costco), `Log_Price_PL = 0.0` ensures the cross-price term `β₃ × Log_Price_PL × has_competitor` = `β₃ × 0.0 × 0` = 0, cleanly zeroing out the effect without NaN propagation.

### 3.10 Refactored: `_apply_retailer_filter()`

**Before:** Inline function defined inside `_clean_data()`.

**After:** Promoted to a method on the class for reuse.

---

## 4. What Did NOT Change

| Component | Status | Why |
|---|---|---|
| `_add_base_and_promo_depth()` | Unchanged | Already handles missing `Base_Price_SI` via proxy logic; the new per-retailer base price computation feeds into it via `Base_Avg_Price` in the cleaned DataFrame |
| `_add_time_features()` | Unchanged | Works on already-parsed `Date` column |
| `_add_seasonal_features()` | Unchanged | Works on already-parsed `Date` column |
| `_handle_missing_features()` | Unchanged | Already config-driven via `retailers` dict |
| `_validate_output()` | Unchanged | Validates final column existence regardless of source |
| Feature engineering methods | Unchanged | `add_interaction_term`, `add_lagged_feature`, etc. operate on final DataFrame |
| `quick_prep()` convenience function | Unchanged | Still accepts same parameters |
| `transform()` pipeline | Unchanged | Same 4-step flow: Load → Clean → Features → Validate |

---

## 5. Data Flow Summary (3 retailers)

```
BJ's CSV (Circana, 74 cols, skiprows=2)
  → _load_single_retailer("BJ's")
  → Product column exists, Circana schema
  → _parse_date: strip "Week Ending ", format %m-%d-%y
  → _compute_avg_price: Dollar Sales / Unit Sales
  → _compute_base_price: Base Dollar Sales / Base Unit Sales
  → Volume Sales: direct column
  → has_promo=1, has_competitor=1

Sam's CSV (Circana, 74 cols, skiprows=2)
  → _load_single_retailer("Sam's Club")
  → [same flow as BJ's]

Costco CSV (CRX, 23 cols, skiprows=1)
  → _load_single_retailer("Costco")
  → Item column → renamed to Product
  → _parse_date: regex "ending (\d{2}-\d{2}-\d{4})", format %m-%d-%Y
  → _compute_avg_price: Avg Net Price (direct column)
  → _compute_base_price: Non Promoted Dollars / Non Promoted Units
      (fallback to Average Price per Unit if NP Units < 500)
  → Volume Sales: Unit Sales × 2.0 (from volume_sales_factor_by_retailer)
  → has_promo=1, has_competitor=0

All three → pd.concat → _clean_data → _create_features → _validate_output
  → Final model-ready DataFrame with uniform schema
```

---

## 6. How to Add a 4th Retailer (Future)

1. Add a new block in `config_template.yaml` under `retailer_data_contracts`
2. Add feature availability flags under `retailers`
3. Add volume factor under `volume_sales_factor_by_retailer` (if no Volume Sales column)
4. Add file path in `data` section
5. Extend `_load_data()` to accept the new path (or generalize to a list)
6. **No changes to transformation logic needed**

---

## 7. Testing Checklist

| Test | How to Verify |
|---|---|
| BJ's still loads correctly | `skiprows=2`, `Product` column, Circana date format |
| Sam's still loads correctly | Same as BJ's |
| Costco loads with `skiprows=1` | Check row count = 1932 (12 items × 161 weeks) |
| Costco `Item` renamed to `Product` | `df.columns` after load |
| Brand filter: only 161 Costco rows after filtering | `"sparkling ice core"` matches aggregate only |
| Date parsing: Costco dates are valid | No NaT values, range Jan 2023 – Jan 2026 |
| Avg price: Costco uses `Avg Net Price` | Promo weeks show ~$12 (not ~$16) |
| Base price: Costco uses `NP$ / NP Units` | ~$16 in all weeks |
| Base price fallback: triggered when NP Units < 500 | Check those 3 weeks use `Average Price per Unit` instead |
| Volume Sales: Costco = `Unit Sales × 2.0` | Verify a few rows |
| `has_promo = 1` for Costco | All Costco rows |
| `has_competitor = 0` for Costco | All Costco rows |
| `Log_Price_PL = 0.0` for Costco | All Costco rows |
| `Promo_Depth_SI` range for Costco | −0.30 to ~0.00 |
| Final DataFrame has uniform schema | Same columns for all retailers |
| BJ's/Sam's results unchanged | Compare output with pre-change `data_prep.py` |

---

## 8. Document History

| Version | Date | Change |
|---|---|---|
| 1.0 | February 5, 2026 | Initial code change contract |
