"""
Example 3: Custom Feature Engineering

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

def main():
    # ============================================================================
    # STEP 1: BASIC DATA PREPARATION
    # ============================================================================

    print("=" * 80)
    print("EXAMPLE 3: CUSTOM FEATURE ENGINEERING")
    print("=" * 80)

    prep = ElasticityDataPrep(
        PrepConfig(
            retailer_filter="Overall",
            include_seasonality=True,
            include_promotions=True,
            verbose=True,
        )
    )

    DATA_DIR = REPO_ROOT / "data"
    bjs_csv = DATA_DIR / "bjs.csv"
    sams_csv = DATA_DIR / "sams.csv"

    if not bjs_csv.exists() or not sams_csv.exists():
        raise FileNotFoundError(
            "Missing input CSV(s). Expected files:\n"
            f"  - {bjs_csv}\n"
            f"  - {sams_csv}\n\n"
            "Place your Circana files in the repo's data/ folder (see README.md)."
        )

    df = prep.transform(bjs_path=str(bjs_csv), sams_path=str(sams_csv))

    print(f"\nBasic data prepared: {len(df)} observations")

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

    df = prep.add_lagged_feature(df, var="Log_Price_SI", lags=[1, 4], group_by=None)

    print("\n✓ Added lagged prices:")
    print("  - Log_Price_SI_lag1 (last week's price)")
    print("  - Log_Price_SI_lag4 (4 weeks ago price)")

    # ============================================================================
    # STEP 4: ADD MOVING AVERAGES
    # ============================================================================

    print("\n" + "=" * 80)
    print("ADDING MOVING AVERAGES")
    print("=" * 80)

    df = prep.add_moving_average(df, var="Price_SI", windows=[4, 8], group_by=None)

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
        "Log_Price_SI",
        "Price_x_Spring",
        "Log_Price_SI_lag1",
        "Price_SI_ma4",
        "Price_Gap",
        "Price_Index",
    ]
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

    # Drop rows with NaN (from lagging) before fitting
    df_clean = df.dropna()
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
