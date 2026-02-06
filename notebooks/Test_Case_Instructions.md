# Data Transformation Validation: Test Case Instructions
## For AI Code Generation

**Purpose:** Write Python test code that validates the `data_prep.py` transformation pipeline produces correct output for BJ's, Sam's Club, and Costco data. These tests should run against the actual CSV files and the `config_template.yaml` configuration.

**Files available:**
- `bjs.csv` — BJ's Circana data (74 columns, skiprows=2)
- `sams.csv` — Sam's Club Circana data (74 columns, skiprows=2)
- `costco.csv` — Costco CRX data (23 columns, skiprows=1)
- `config_template.yaml` — Configuration with retailer_data_contracts
- `data_prep.py` — The transformation pipeline to test

---

## TEST GROUP 1: Raw File Loading

### Test 1.1 — BJ's loads with correct schema
- Load `bjs.csv` with `skiprows=2`
- Assert column count = 74
- Assert `Product` column exists
- Assert `Time` column exists
- Assert `Base Dollar Sales` column exists
- Assert `Base Unit Sales` column exists
- Assert `Volume Sales` column exists
- Assert total rows = 477

### Test 1.2 — Sam's loads with correct schema
- Load `sams.csv` with `skiprows=2`
- Assert column count = 74
- Assert `Product` column exists
- Assert same columns as BJ's (identical Circana schema)
- Assert total rows = 477

### Test 1.3 — Costco loads with correct schema
- Load `costco.csv` with `skiprows=1` (NOT 2)
- Assert column count = 23
- Assert `Item` column exists (NOT `Product`)
- Assert `Avg Net Price` column exists
- Assert `Non Promoted Dollars` column exists
- Assert `Non Promoted Units` column exists
- Assert `Average Price per Unit` column exists
- Assert `Volume Sales` column does NOT exist
- Assert `Base Dollar Sales` column does NOT exist
- Assert total rows = 1932

### Test 1.4 — Costco Item column renamed to Product after load
- Run `_load_single_retailer()` for Costco
- Assert output DataFrame has column `Product` (not `Item`)
- Assert output DataFrame has `Retailer` column = "Costco" for all rows

---

## TEST GROUP 2: Product Filtering

### Test 2.1 — BJ's brand filtering
- After filtering BJ's data on fuzzy match `"sparkling ice"`, assert exactly 159 rows of Sparkling Ice
- After filtering on `"private label"`, assert exactly 318 rows of Private Label
- Total filtered rows = 477

### Test 2.2 — Sam's brand filtering
- Same as BJ's: 159 SI rows, 318 PL rows, 477 total

### Test 2.3 — Costco brand filtering with "sparkling ice core"
- After filtering Costco `Item` column on fuzzy match `"sparkling ice core"`, assert exactly 161 rows
- These 161 rows should all have `Item` = `"Sparkling Ice Core 17oz 24ct 2023 through 2025 Items"`
- The 11 individual UPC rows (e.g., `"ITEM 001422384 SPARKLING ICE FRUIT BLST VTY PK..."`) must NOT be included
- Assert 0 Private Label rows for Costco

### Test 2.4 — Costco UPC rows excluded
- Verify that no rows where `Item` starts with `"ITEM "` survive the filtering
- This is the critical test that `"sparkling ice core"` works and `"sparkling ice"` alone would fail
- Count rows matching `"sparkling ice"` (should be 1932 = 12 items × 161 weeks)
- Count rows matching `"sparkling ice core"` (should be 161 = 1 item × 161 weeks)

---

## TEST GROUP 3: Date Parsing

### Test 3.1 — BJ's date parsing
- Input: `"Week Ending 01-08-23"`
- Expected output: `pd.Timestamp('2023-01-08')`
- Assert no NaT values after parsing
- Assert date range: min = 2023-01-08, max = 2026-01-18
- Assert 159 unique dates for Sparkling Ice

### Test 3.2 — Sam's date parsing
- Same format as BJ's
- Assert same date range: 2023-01-08 to 2026-01-18

### Test 3.3 — Costco date parsing (different format)
- Input: `"1 week ending 01-08-2023"` (note: 4-digit year, "1 week" prefix)
- Expected output: `pd.Timestamp('2023-01-08')`
- Assert regex extraction of `"ending (\d{2}-\d{2}-\d{4})"` produces valid dates
- Assert no NaT values after parsing
- Assert date range: min = 2023-01-01, max = 2026-01-25
- Assert 161 unique dates for brand aggregate

### Test 3.4 — All three retailers have overlapping date ranges
- All three should have data spanning Jan 2023 through Jan 2026
- Verify at least 150 weeks of overlap between all three

---

## TEST GROUP 4: Price Calculations (CRITICAL)

### Test 4.1 — BJ's average price = Dollar Sales / Unit Sales
- For each BJ's SI row: `Avg_Price = Dollar Sales / Unit Sales`
- Assert range: $15.68 – $19.67
- Assert no NaN or inf values

### Test 4.2 — Sam's average price = Dollar Sales / Unit Sales
- Same formula as BJ's
- Assert range: $12.32 – $17.90

### Test 4.3 — Costco average price = Avg Net Price (NOT Dollar Sales / Unit Sales)
- For each Costco brand aggregate row: `Avg_Price` must equal the `Avg Net Price` column value
- Assert `Avg_Price` is NOT equal to `Dollar Sales / Unit Sales` (which gives shelf price ~$16)
- Assert range: $11.71 – $18.05
- **Specific validation:** For promo week `"1 week ending 02-05-2023"`:
  - `Avg Net Price` ≈ $12.06 (correct — net of coupons)
  - `Dollar Sales / Unit Sales` ≈ $16.01 (wrong — this is shelf price)
  - Assert the pipeline uses $12.06, not $16.01

### Test 4.4 — BJ's base price = Base Dollar Sales / Base Unit Sales
- Assert `Base_Price_SI` is computed from Circana's modeled base columns
- Assert range: $16.82 – $19.68
- Assert no NaN values

### Test 4.5 — Sam's base price = Base Dollar Sales / Base Unit Sales
- Same formula as BJ's
- Assert range: $15.53 – $17.90

### Test 4.6 — Costco base price = Non Promoted Dollars / Non Promoted Units
- Assert `Base_Price_SI` is computed from `Non Promoted Dollars / Non Promoted Units`
- Assert range: $15.74 – $18.05
- Assert no NaN values
- **Fallback test:** For weeks where `Non Promoted Units < 500` (there are 3 such weeks):
  - Assert `Base_Price_SI` uses `Average Price per Unit` instead
  - Verify the fallback value is reasonable (within $15.50 – $18.50)

### Test 4.7 — Costco base price is NOT Average Price per Unit for normal weeks
- For weeks where `Non Promoted Units >= 500`, assert `Base_Price_SI` equals `Non Promoted Dollars / Non Promoted Units`, NOT `Average Price per Unit`
- The two values are close (~$16.02 vs ~$16.03) but should not be identical

---

## TEST GROUP 5: Promo Depth

### Test 5.1 — Promo depth formula consistent across all retailers
- For all retailers: `Promo_Depth_SI = (Price_SI / Base_Price_SI) - 1`
- Assert this formula is used (not some other definition)

### Test 5.2 — BJ's promo depth range
- Assert range: approximately -0.15 to +0.01
- Most weeks should be near 0 or slightly negative

### Test 5.3 — Sam's promo depth range
- Assert range: approximately -0.30 to +0.01
- Sam's has deeper discounts than BJ's

### Test 5.4 — Costco promo depth range
- Assert range: approximately -0.30 to +0.001
- Non-promo weeks (102 of 161): `|Promo_Depth_SI|` < 0.01
- Promo weeks (59 of 161): `Promo_Depth_SI` significantly negative (e.g., -0.25 for heavy promo)
- **Specific validation:** Week `"1 week ending 02-05-2023"`:
  - Avg Net Price ≈ $12.06, NP Base Price ≈ $16.03
  - Promo_Depth ≈ (12.06 / 16.03) - 1 ≈ -0.248
- **Specific validation:** Week `"1 week ending 01-01-2023"` (non-promo):
  - Promo_Depth ≈ 0.000 (within ±0.001)

### Test 5.5 — Promo depth clipping
- Assert all values are within [-0.80, 0.50] (the clip range in code)

---

## TEST GROUP 6: Volume Sales

### Test 6.1 — BJ's Volume Sales = direct column
- Assert `Volume_Sales_SI` equals the `Volume Sales` column from the CSV
- Assert `Volume Sales / Unit Sales` ratio = 2.0000 for all rows

### Test 6.2 — Sam's Volume Sales = direct column
- Same as BJ's: ratio = 2.0000

### Test 6.3 — Costco Volume Sales = Unit Sales × 2.0
- Assert `Volume_Sales_SI = Unit Sales × 2.0` for all Costco rows
- Assert no NaN or zero values
- Assert range: 68,090 (34,045 × 2) to 513,518 (256,759 × 2)

---

## TEST GROUP 7: Availability Masks

### Test 7.1 — BJ's masks
- Assert `has_promo = 1` for all BJ's rows
- Assert `has_competitor = 1` for all BJ's rows

### Test 7.2 — Sam's masks
- Assert `has_promo = 1` for all Sam's rows
- Assert `has_competitor = 1` for all Sam's rows

### Test 7.3 — Costco masks
- Assert `has_promo = 1` for all Costco rows
- Assert `has_competitor = 0` for all Costco rows

### Test 7.4 — Costco Log_Price_PL = 0.0
- Assert `Log_Price_PL = 0.0` for all Costco rows
- Assert `Log_Price_PL` is NOT NaN for Costco rows (must be 0.0, not missing)

### Test 7.5 — BJ's/Sam's Log_Price_PL > 0
- Assert `Log_Price_PL > 0` for all BJ's and Sam's rows (valid log of positive PL price)

---

## TEST GROUP 8: Log Transformations

### Test 8.1 — Log Volume Sales
- Assert `Log_Volume_Sales_SI = ln(Volume_Sales_SI)` for all rows
- Assert no NaN or inf values
- Assert range: approximately 9.5 to 13.5

### Test 8.2 — Log Base Price
- Assert `Log_Base_Price_SI = ln(Base_Price_SI)` for all rows
- Assert no NaN or inf values
- Assert range: approximately 2.70 to 3.00

### Test 8.3 — Log Price PL
- For BJ's/Sam's: `Log_Price_PL = ln(Price_PL)` where Price_PL > 0
- For Costco: `Log_Price_PL = 0.0`
- Assert no NaN values anywhere

---

## TEST GROUP 9: Seasonality and Time Features

### Test 9.1 — Seasonal dummies are mutually exclusive with Winter
- For each row: at most one of `Spring`, `Summer`, `Fall` = 1
- Winter (Dec, Jan, Feb) has all three = 0
- `Spring` = 1 ↔ month in {3, 4, 5}
- `Summer` = 1 ↔ month in {6, 7, 8}
- `Fall` = 1 ↔ month in {9, 10, 11}

### Test 9.2 — Week_Number is monotonically increasing per retailer
- Within each retailer, `Week_Number` should increase (or stay same) with Date
- `Week_Number` = 0 for the earliest date in the combined dataset

### Test 9.3 — Week_Number is globally consistent
- The same calendar date should have the same `Week_Number` across all retailers

---

## TEST GROUP 10: Final Output Schema

### Test 10.1 — Required columns present
- Assert these columns exist in the final DataFrame:
  `Date`, `Retailer`, `Log_Volume_Sales_SI`, `Log_Base_Price_SI`, `Promo_Depth_SI`,
  `Log_Price_PL`, `Log_Price_SI`, `Price_SI`, `Base_Price_SI`, `Volume_Sales_SI`,
  `Spring`, `Summer`, `Fall`, `Week_Number`, `has_promo`, `has_competitor`,
  `Promo_Intensity_SI`

### Test 10.2 — Row counts per retailer
- BJ's: approximately 159 rows (one per week, SI only after pivot)
- Sam's: approximately 159 rows
- Costco: approximately 161 rows
- Total: approximately 479 rows

### Test 10.3 — No duplicate Date-Retailer combinations
- Assert `df.duplicated(subset=['Date', 'Retailer']).sum() == 0`

### Test 10.4 — No NaN in critical columns
- Assert zero NaN in: `Log_Volume_Sales_SI`, `Log_Base_Price_SI`, `Promo_Depth_SI`, `Log_Price_PL`, `has_promo`, `has_competitor`

### Test 10.5 — Data types
- `Date` should be datetime64
- All numeric columns should be float64 or int64
- `Retailer` should be object/string

---

## TEST GROUP 11: Cross-Retailer Consistency

### Test 11.1 — Promo_Depth formula is the same for all
- Verify: `Promo_Depth_SI ≈ (Price_SI / Base_Price_SI) - 1` for ALL retailers (tolerance: 0.001)
- This confirms the pipeline applies a uniform formula, even though the input columns differ

### Test 11.2 — BJ's/Sam's results unchanged from pre-Costco pipeline
- Run the pipeline with `costco_path=None` (BJ's + Sam's only)
- Run the pipeline with `costco_path='costco.csv'` (all three)
- Assert that BJ's and Sam's rows in the 3-retailer output are identical to the 2-retailer output
- Adding Costco must NOT change any BJ's or Sam's values

### Test 11.3 — Base_Price_SI >= Price_SI in most weeks
- For all retailers, `Base_Price_SI >= Price_SI` should hold in >90% of rows
- (Base price is the regular price; avg price is lower when discounted)

---

## TEST GROUP 12: Costco-Specific Edge Cases

### Test 12.1 — Heavy promo week validation (02-05-2023)
- Find the Costco row for week ending 2023-02-05
- Assert `Avg Net Price ≈ 12.06` (tolerance: $0.10)
- Assert `Base_Price_SI ≈ 16.03` (tolerance: $0.10)
- Assert `Promo_Depth_SI ≈ -0.248` (tolerance: 0.01)
- Assert `Volume_Sales_SI ≈ 178136 × 2 = 356272` (tolerance: 100)

### Test 12.2 — Non-promo week validation (01-01-2023)
- Find the Costco row for week ending 2023-01-01
- Assert `|Promo_Depth_SI| < 0.001`
- Assert `Price_SI ≈ Base_Price_SI` (tolerance: $0.05)

### Test 12.3 — Low NP Units fallback (week of 02-11-2024)
- This week has Non Promoted Units = 487 (below 500 threshold)
- Assert `Base_Price_SI` equals `Average Price per Unit` for this row (not NP$/NP Units)
- Assert `Average Price per Unit ≈ 15.99` for this week (tolerance: $0.10)

### Test 12.4 — Costco Dollar Sales is NOT used for Avg_Price
- For ALL Costco rows: assert `Price_SI != Dollar Sales / Unit Sales` (within tolerance of $0.10)
- Specifically for promo weeks: the difference should be > $1.00 (shelf price ~$16 vs net ~$12)

---

## NOTES FOR THE AI CODE WRITER

1. **Framework:** Use `pytest` with descriptive test names and clear assertion messages.

2. **Fixtures:** Create a shared fixture that runs the full pipeline once and caches the result:
   ```python
   @pytest.fixture(scope="session")
   def pipeline_result():
       # Load config from config_template.yaml
       # Instantiate PrepConfig with all relevant settings
       # Run transform(bjs_path, sams_path, costco_path)
       # Return the final DataFrame
   ```

3. **Tolerances:** Use `pytest.approx()` for floating-point comparisons. Price tolerances: $0.10. Ratio tolerances: 0.001. Promo depth tolerances: 0.01.

4. **File paths:** Assume all files are in the same directory. Use relative paths.

5. **Config loading:** Parse `config_template.yaml` with `yaml.safe_load()` and construct a `PrepConfig` from the `data` section, including `retailer_data_contracts`, `retailers`, and `volume_sales_factor_by_retailer`.

6. **Independence:** Each test group should be independent. If one test fails, the others should still run.

7. **Reporting:** On failure, print the actual vs expected values and the row(s) that failed.
