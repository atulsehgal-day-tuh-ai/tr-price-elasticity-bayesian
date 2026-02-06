"""
Example 3: Custom Feature Engineering (retailer × week shape; optional Costco)

This example demonstrates:
- Adding interaction terms (price × season)
- Adding lagged features (past prices)
- Adding moving averages (reference prices)
- Adding custom features with formulas
- Testing effects in the model

Use this when:
- Want to test if elasticity varies by season
- Want to include momentum/carryover effects
- Need custom transformations
- Testing specific hypotheses

Retailer note:
- This example always requires `data/bjs.csv` and `data/sams.csv`.
- If `data/costco.csv` exists, the example will automatically include Costco as well.
- This example keeps retailers separate (`retailer_filter="All"`) so the transformed dataset is
  one row per (Retailer, Week). This mirrors the hierarchical-path data shape and ensures
  lagged/moving-average features are computed **within retailer** (no cross-retailer leakage).
"""

import sys
from pathlib import Path

# Allow running this file directly: `python examples/example_03_add_features.py`
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data_prep import ElasticityDataPrep, PrepConfig
from bayesian_models import SimpleBayesianModel
import pandas as pd
import numpy as np
import yaml

def main():
    # ============================================================================
    # STEP 1: BASIC DATA PREPARATION
    # ============================================================================

    print("=" * 80)
    print("EXAMPLE 3: CUSTOM FEATURE ENGINEERING")
    print("=" * 80)

    DATA_DIR = REPO_ROOT / "data"
    bjs_csv = DATA_DIR / "bjs.csv"
    sams_csv = DATA_DIR / "sams.csv"
    costco_csv = DATA_DIR / "costco.csv"
    include_costco = costco_csv.exists()

    if not bjs_csv.exists() or not sams_csv.exists():
        raise FileNotFoundError(
            "Missing input CSV(s). Expected files:\n"
            f"  - {bjs_csv}\n"
            f"  - {sams_csv}\n\n"
            "Place your Circana files in the repo's data/ folder (see README.md)."
        )

    # Load runtime retailer contracts from config_template.yaml so heterogeneous sources (Costco CRX)
    # can be parsed correctly without hardcoding retailer logic in this script.
    retailer_data_contracts = None
    try:
        cfg_path = REPO_ROOT / "config_template.yaml"
        with open(cfg_path, "r") as f:
            cfg_yaml = yaml.safe_load(f) or {}
        retailer_data_contracts = (cfg_yaml.get("data") or {}).get("retailer_data_contracts")
    except Exception:
        retailer_data_contracts = None

    # Always keep retailers separate so time-series features (lags/MAs) are computed
    # within each retailer, and the dataset shape mirrors the hierarchical-path flow.
    retailer_filter = "All"

    retailers_cfg = {
        "BJs": {"has_promo": True, "has_competitor": True},
        "Sams": {"has_promo": True, "has_competitor": True},
    }
    if include_costco:
        retailers_cfg["Costco"] = {"has_promo": True, "has_competitor": False}

    prep = ElasticityDataPrep(
        PrepConfig(
            retailer_filter=retailer_filter,
            include_seasonality=True,
            include_promotions=True,
            verbose=True,
            separate_base_promo=True,
            volume_sales_factor_by_retailer={"Costco": 2.0},
            retailers=retailers_cfg,
            retailer_data_contracts=retailer_data_contracts,
        )
    )

    df = prep.transform(
        bjs_path=str(bjs_csv),
        sams_path=str(sams_csv),
        costco_path=str(costco_csv) if include_costco else None,
    )

    print(f"\nBasic data prepared: {len(df)} observations")
    if "Retailer" in df.columns:
        print(f"Retailers: {df['Retailer'].unique().tolist()}")

    # ============================================================================
    # STEP 2: ADD INTERACTION TERMS
    # ============================================================================

    print("\n" + "=" * 80)
    print("ADDING INTERACTION TERMS")
    print("=" * 80)

    df = prep.add_interaction_term(df, var1="Log_Price_SI", var2="Spring", name="Price_x_Spring")
    df = prep.add_interaction_term(df, var1="Log_Price_SI", var2="Summer", name="Price_x_Summer")

    print("\n✓ Added interaction terms:")
    print("  - Price_x_Spring (tests Spring-specific price sensitivity)")
    print("  - Price_x_Summer (tests Summer-specific price sensitivity)")

    # ============================================================================
    # STEP 3: ADD LAGGED FEATURES
    # ============================================================================

    print("\n" + "=" * 80)
    print("ADDING LAGGED FEATURES")
    print("=" * 80)

    # If we have multiple retailers, compute lags within retailer to avoid mixing time series.
    group_by = ["Retailer"] if "Retailer" in df.columns else None
    df = prep.add_lagged_feature(df, var="Log_Price_SI", lags=[1, 4], group_by=group_by)

    print("\n✓ Added lagged prices:")
    print("  - Log_Price_SI_lag1 (last week's price)")
    print("  - Log_Price_SI_lag4 (4 weeks ago price)")

    # ============================================================================
    # STEP 4: ADD MOVING AVERAGES
    # ============================================================================

    print("\n" + "=" * 80)
    print("ADDING MOVING AVERAGES")
    print("=" * 80)

    df = prep.add_moving_average(df, var="Price_SI", windows=[4, 8], group_by=group_by)

    print("\n✓ Added moving averages:")
    print("  - Price_SI_ma4 (4-week average price)")
    print("  - Price_SI_ma8 (8-week average price)")

    # ============================================================================
    # STEP 5: ADD CUSTOM FEATURES
    # ============================================================================

    print("\n" + "=" * 80)
    print("ADDING CUSTOM FEATURES")
    print("=" * 80)

    df = prep.add_custom_feature(df, name="Price_Gap", formula=lambda d: d["Price_SI"] - d["Price_PL"])
    df = prep.add_custom_feature(df, name="Price_Index", formula=lambda d: d["Price_SI"] / d["Price_SI_ma4"])

    df = prep.add_custom_feature(
        df,
        name="Log_Price_Gap",
        formula=lambda d: pd.Series(
            [0 if g <= 0 else np.log(g) for g in d["Price_Gap"]],
            index=d.index,
        ),
    )

    print("\n✓ Added custom features:")
    print("  - Price_Gap = Price_SI - Price_PL")
    print("  - Price_Index = Price_SI / Price_SI_ma4")
    print("  - Log_Price_Gap = log(max(Price_Gap, 0))")

    # ============================================================================
    # STEP 6: INSPECT NEW FEATURES
    # ============================================================================

    print("\n" + "=" * 80)
    print("INSPECTING NEW FEATURES")
    print("=" * 80)

    feature_cols = [
        "Date",
        "Retailer",
        "Log_Price_SI",
        "Price_x_Spring",
        "Log_Price_SI_lag1",
        "Price_SI_ma4",
        "Price_Gap",
        "Price_Index",
    ]
    feature_cols = [c for c in feature_cols if c in df.columns]
    print("\nSample of enhanced data:")
    print(df[feature_cols].head(10))

    # ============================================================================
    # STEP 7: FIT MODEL (BASELINE) + NOTE ON EXTENDING FEATURES
    # ============================================================================

    print("\n" + "=" * 80)
    print("FITTING MODEL WITH CUSTOM FEATURES (BASELINE RUN)")
    print("=" * 80)

    print(
        """
NOTE:
- The current SimpleBayesianModel uses a fixed set of core features.
- You CAN still engineer features (as above) for exploration and correlation checks.
- To include custom features in the PyMC model, you’d extend bayesian_models.py to add coefficients and terms in the linear predictor.
"""
    )

    # ------------------------------------------------------------------------
    # Cleaning for modeling (avoid dropping heterogeneous retailers)
    # ------------------------------------------------------------------------
    # Important: retailers like Costco may legitimately have missing competitor/private-label columns.
    # A blanket df.dropna() would delete those rows. Instead:
    #   - Fill competitor columns for has_competitor == 0 retailers
    #   - Drop NaNs only for columns that become NaN due to lag/MA feature creation

    if "has_competitor" in df.columns:
        for c in ["Volume_Sales_PL", "Price_PL", "Log_Price_PL"]:
            if c in df.columns:
                df.loc[df["has_competitor"] == 0, c] = 0.0

    required_for_modeling = [
        "Log_Volume_Sales_SI",
        "Log_Price_SI",
        "Log_Price_SI_lag1",
        "Log_Price_SI_lag4",
        "Price_SI_ma4",
        "Price_SI_ma8",
        "Price_Gap",
        "Price_Index",
    ]
    required_for_modeling = [c for c in required_for_modeling if c in df.columns]

    # Drop rows with NaN only where it matters for this example's baseline fit
    df_clean = df.dropna(subset=required_for_modeling).copy()
    print(f"After dropping NaN from lags: {len(df_clean)} rows")

    model = SimpleBayesianModel(priors="default", n_samples=1000, n_chains=2, verbose=True)
    _ = model.fit(df_clean)

    # ============================================================================
    # STEP 8: FEATURE CORRELATION QUICK-CHECK
    # ============================================================================

    print("\n" + "=" * 80)
    print("ANALYZING FEATURE CORRELATIONS")
    print("=" * 80)

    correlations = df_clean[
        [
            "Log_Volume_Sales_SI",
            "Log_Price_SI",
            "Log_Price_SI_lag1",
            "Log_Price_SI_lag4",
            "Price_Gap",
            "Price_Index",
        ]
    ].corr()["Log_Volume_Sales_SI"].sort_values(ascending=False)

    print("\nCorrelations with Log Sales:")
    print(correlations)

    # ============================================================================
    # STEP 9: SAVE ENHANCED DATA
    # ============================================================================

    print("\n" + "=" * 80)
    print("SAVING ENHANCED DATA")
    print("=" * 80)

    out_dir = REPO_ROOT / "output_example_03"
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = out_dir / "enhanced_data.csv"
    df_clean.to_csv(output_path, index=False)

    print(f"\n✓ Enhanced data saved to: {output_path}")
    print(f"  Contains {len(df_clean.columns)} columns")

    print("\n" + "=" * 80)
    print("✓ EXAMPLE 3 COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
