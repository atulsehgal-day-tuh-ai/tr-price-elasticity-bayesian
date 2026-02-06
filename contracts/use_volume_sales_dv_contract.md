---
name: Use Volume Sales DV
overview: Refactor the pipeline to always model log(Volume Sales) as the dependent variable, while keeping price and promo-depth calculations based on Unit Sales; add a strict fallback to compute Volume Sales from Unit Sales via a configured retailer-level factor (else fail hard).
source: Copied from Cursor plan `use_volume_sales_dv_58369333.plan.md` for long-term reference.
---

# Always use Volume Sales as dependent variable

## Goal
Update the pipeline so the model uses **`Volume Sales`** as the dependent variable whenever possible, and when it is missing (e.g., Costco) it is computed from `Unit Sales × factor` using a configured constant. Keep all price and promo-depth computations based on **Unit Sales denominators** to avoid unit mismatches.

## Key behavior (hard rule)
- **Dependent variable**: always `Log_Volume_Sales_SI`.
- **If `Volume Sales` exists** in the raw CSV: use it.
- **Else if `Unit Sales` exists** and a **retailer-level constant factor** is provided in config: compute `Volume Sales = Unit Sales × factor`.
- **Else**: fail fast with a clear error explaining what’s missing and how to fix it.
- **Prices & promo depth** remain unchanged:
  - `Avg_Price_SI = Dollar Sales / Unit Sales`
  - `Base_Price_SI = Base Dollar Sales / Base Unit Sales`
  - `Promo_Depth_SI = (Avg_Price_SI / Base_Price_SI) - 1`

## Files to change
- `data_prep.py`
  - In `_clean_data()`: ingest `Volume Sales` if present; otherwise create it from `Unit Sales` using config factor (per retailer, constant).
  - In `_pivot_to_wide()`: pivot sales using `Volume Sales` (Sparkling Ice and Private Label if needed), producing `Volume_Sales_SI`.
  - In `_create_features()`: compute `Log_Volume_Sales_SI = log(Volume_Sales_SI)` and stop using `Log_Unit_Sales_SI` as the required outcome column.
  - Add validation that `Volume_Sales_SI > 0` after fallback.
- `bayesian_models.py`
  - Replace `y = data['Log_Unit_Sales_SI']` with `y = data['Log_Volume_Sales_SI']` (and keep everything else the same).
  - Ensure any downstream references to unit-sales outcome are updated consistently.
- `README.md` and `help_documents/architecture.md`
  - Update the “dependent variable” description to reflect Volume Sales.
  - Document the strict fallback rule and how to configure the factor.

## Configuration change
- Extend `PrepConfig` in `data_prep.py` to support a mapping like:
  - `volume_sales_factor_by_retailer: dict[str, float]` (e.g., `{ "Costco": 2.0 }`)
- Extend `config_template.yaml` (or whichever config is used) to include this field.

## Acceptance checks
- Running data prep on BJ’s/Sam’s data with `Volume Sales` present produces `Log_Volume_Sales_SI` and the model fits without touching price calculations.
- Running data prep on Costco without `Volume Sales` but with configured factor produces `Volume_Sales_SI` and runs end-to-end.
- Running Costco without `Volume Sales` and without a factor fails with a clear error message.

