"""
Example 4: Adding Costco with Missing Data

This example demonstrates (V2):
- Adding a third retailer (Costco) with incomplete data
- Configuring retailer-specific features
- Handling missing promotional data
- Hierarchical model with 3 retailers
- Automatic model adjustment

Use this when:
- Adding new retailers with different data availability
- Some retailers lack certain features (promo, competitor, etc.)
- Want to include all available data without manual filtering
"""

import sys
from pathlib import Path

# Allow running this file directly: `python examples/example_04_costco.py`
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data_prep import ElasticityDataPrep, PrepConfig
from bayesian_models import HierarchicalBayesianModel
from visualizations import generate_html_report

def main():
    # ============================================================================
    # STEP 1: CONFIGURE RETAILER-SPECIFIC SETTINGS
    # ============================================================================

    print("=" * 80)
    print("EXAMPLE 4: ADDING COSTCO WITH MISSING DATA")
    print("=" * 80)

    print(
        """
Scenario:
--------
You have data for BJ's, Sam's, and Costco, but:
- BJ's: Full data (sales, price, promo, competitor)
- Sam's: Full data (sales, price, promo, competitor)
- Costco: Partial data (sales, price, competitor, but NO promo)

The system will automatically handle this using:
- Safe defaults for missing features (e.g., promo = 0)
- Availability flags (e.g., has_promo = 0)
- Masking in the model so missing features don’t bias estimation
"""
    )

    retailer_config = {
        "BJs": {"has_promo": True, "has_competitor": True},
        "Sams": {"has_promo": True, "has_competitor": True},
        "Costco": {"has_promo": False, "has_competitor": True},  # Costco: NO promo columns
    }

    # ============================================================================
    # STEP 2: DATA PREP (WITH MISSING DATA HANDLING)
    # ============================================================================

    print("\n" + "=" * 80)
    print("DATA PREPARATION (WITH MISSING DATA HANDLING)")
    print("=" * 80)

    prep = ElasticityDataPrep(
        PrepConfig(
            retailer_filter="All",
            include_seasonality=True,
            include_promotions=True,
            # If a retailer file is missing `Volume Sales`, data prep can compute it as:
            #   Volume Sales = Unit Sales × factor
            # Provide factors here (retailer name → constant).
            volume_sales_factor_by_retailer={"Costco": 2.0},
            separate_base_promo=True,
            retailers=retailer_config,
            verbose=True,
        )
    )

    DATA_DIR = REPO_ROOT / "data"
    bjs_csv = DATA_DIR / "bjs.csv"
    sams_csv = DATA_DIR / "sams.csv"
    costco_csv = DATA_DIR / "costco.csv"

    missing = [p for p in [bjs_csv, sams_csv, costco_csv] if not p.exists()]
    if missing:
        raise FileNotFoundError(
            "Missing input CSV(s). Expected files:\n"
            + "\n".join([f"  - {p}" for p in [bjs_csv, sams_csv, costco_csv]])
            + "\n\nPlace your Circana files in the repo's data/ folder (see README.md)."
        )

    df = prep.transform(bjs_path=str(bjs_csv), sams_path=str(sams_csv), costco_path=str(costco_csv))

    print(f"\nData prepared: {len(df)} observations")
    print(f"Retailers: {df['Retailer'].unique().tolist()}")

    # ============================================================================
    # STEP 3: INSPECT DATA AVAILABILITY
    # ============================================================================

    print("\n" + "=" * 80)
    print("DATA AVAILABILITY CHECK")
    print("=" * 80)

    # Show has_promo by retailer (if present)
    if "has_promo" in df.columns:
        print("\nhas_promo by retailer:")
        print(df.groupby("Retailer")["has_promo"].max())

    # Show a few columns for sanity
    sample_cols = ["Date", "Retailer", "Log_Price_SI"]
    for col in ["Promo_Depth_SI", "Promo_Intensity_SI", "has_promo", "has_competitor"]:
        if col in df.columns:
            sample_cols.append(col)

    print("\nSample rows:")
    print(df[sample_cols].head(10))

    # ============================================================================
    # STEP 4: FIT HIERARCHICAL MODEL
    # ============================================================================

    print("\n" + "=" * 80)
    print("FITTING HIERARCHICAL MODEL (3 RETAILERS)")
    print("=" * 80)

    model = HierarchicalBayesianModel(
        priors="default",
        n_samples=2000,
        n_chains=4,
        n_tune=1000,
        random_seed=42,
        verbose=True,
    )

    results = model.fit(df)

    print("\n" + "=" * 80)
    print("MODEL SUMMARY")
    print("=" * 80)
    print(results.summary())

    # ============================================================================
    # STEP 5: REPORT
    # ============================================================================

    print("\n" + "=" * 80)
    print("GENERATING REPORT")
    print("=" * 80)

    out_dir = REPO_ROOT / "output_example_04"
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = generate_html_report(
        results=results,
        data=df,
        output_dir=str(out_dir),
        report_name="costco_missing_promo_report.html",
    )

    print(f"\n✓ Report generated: {report_path}")
    print("\n" + "=" * 80)
    print("✓ EXAMPLE 4 COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
