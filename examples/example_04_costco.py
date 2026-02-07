"""
Example 4: Hierarchical + Costco (heterogeneous schema + missing-feature masking)

This example demonstrates (V2):
- Adding a third retailer (Costco CRX) with a **different schema** than Circana
- Configuring retailer-specific feature availability (masks via `has_promo` / `has_competitor`)
- Handling missing competitor/private label features safely (masking instead of manual filtering)
- Handling missing `Volume Sales` via a strict fallback: `Unit Sales × factor` (per retailer)
- Hierarchical model with 3 retailers (partial pooling)

Use this when:
- Adding new retailers with different schemas and/or data availability
- Some retailers lack certain features (competitor/private label, promo, etc.)
- You want one model that can include all retailers without manual, per-retailer branching
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
import yaml

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
        # Costco CRX: no Private Label columns (competitor), and promo feature availability can be
        # treated as "missing" for masking demonstrations (promo features safely default to 0).
        "Costco": {"has_promo": False, "has_competitor": False},
    }

    # ============================================================================
    # STEP 2: DATA PREP (WITH MISSING DATA HANDLING)
    # ============================================================================

    print("\n" + "=" * 80)
    print("DATA PREPARATION (WITH MISSING DATA HANDLING)")
    print("=" * 80)

    # Load runtime retailer contracts from config_template.yaml so heterogeneous sources (Costco CRX)
    # are parsed correctly (skiprows, product column rename, date parsing, price formulas, etc.).
    retailer_data_contracts = None
    try:
        cfg_path = REPO_ROOT / "config_template.yaml"
        with open(cfg_path, "r") as f:
            cfg_yaml = yaml.safe_load(f) or {}
        retailer_data_contracts = (cfg_yaml.get("data") or {}).get("retailer_data_contracts")
    except Exception:
        retailer_data_contracts = None

    if retailer_data_contracts is None:
        print(
            "\n⚠️  WARNING: Could not load runtime retailer_data_contracts from config_template.yaml.\n"
            "    Costco will be parsed using legacy Circana defaults and may be dropped during cleaning.\n"
            "    Fix: ensure config_template.yaml exists and PyYAML is installed.\n"
        )

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
            retailer_data_contracts=retailer_data_contracts,
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
    report_paths = generate_html_report(
        results=results,
        data=df,
        output_dir=str(out_dir),
    )

    print(f"\n✓ Reports generated:")
    for k, v in report_paths.items():
        print(f"  - {k}: {v}")
    print("\n" + "=" * 80)
    print("✓ EXAMPLE 4 COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
