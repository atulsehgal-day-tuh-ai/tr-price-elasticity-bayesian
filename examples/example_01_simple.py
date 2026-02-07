"""
Example 1: Simple Bayesian Model - Basic Usage

This example demonstrates (V2):
- Basic data preparation (including base price + promo depth features)
- Fitting a simple (non-hierarchical) Bayesian model with dual elasticities
- Viewing results
- Probability statements
- Revenue scenarios (base price vs promotions)

Use this when:
- Analyzing overall data (BJ's + Sam's combined)
- Single retailer analysis
- Getting started with the system
"""

import sys
from pathlib import Path

# Allow running this file directly: `python examples/example_01_simple.py`
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data_prep import ElasticityDataPrep, PrepConfig
from bayesian_models import SimpleBayesianModel
from visualizations import generate_html_report

def main():
    # ============================================================================
    # STEP 1: DATA PREPARATION
    # ============================================================================

    print("="*80)
    print("EXAMPLE 1: SIMPLE BAYESIAN MODEL")
    print("="*80)

    # Configure data preparation
    # Use 'Overall' to combine BJ's and Sam's into one pooled dataset
    prep_config = PrepConfig(
        retailer_filter='Overall',  # Combine retailers
        include_seasonality=True,
        include_promotions=True,
        separate_base_promo=True,   # V2: base vs promo separation (default-on)
        verbose=True
    )

    # Initialize prep
    prep = ElasticityDataPrep(prep_config)

    # Transform data
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

    df = prep.transform(
        bjs_path=str(bjs_csv),
        sams_path=str(sams_csv),
    )

    print(f"\nData prepared: {len(df)} observations")
    print(f"Date range: {df['Date'].min()} to {df['Date'].max()}")

    # ============================================================================
    # STEP 2: FIT BAYESIAN MODEL
    # ============================================================================

    print("\n" + "="*80)
    print("FITTING SIMPLE BAYESIAN MODEL")
    print("="*80)

    # Create model with default priors (recommended)
    model = SimpleBayesianModel(
        priors='default',      # Use weakly informative priors
        n_samples=2000,        # Number of posterior samples
        n_chains=4,            # Number of MCMC chains
        n_tune=1000,           # Tuning/burn-in steps
        random_seed=42,
        verbose=True
    )

    # Fit model
    results = model.fit(df)

    # ============================================================================
    # STEP 3: VIEW RESULTS
    # ============================================================================

    print("\n" + "="*80)
    print("RESULTS SUMMARY")
    print("="*80)

    # Print full summary
    print(results.summary())

    # ============================================================================
    # STEP 4: SPECIFIC QUERIES
    # ============================================================================

    print("\n" + "="*80)
    print("SPECIFIC QUERIES")
    print("="*80)

    # Point estimates
    print(f"\nBase Price Elasticity:")
    print(f"  Mean: {results.base_elasticity.mean:.3f}")
    print(f"  Median: {results.base_elasticity.median:.3f}")
    print(f"  95% CI: [{results.base_elasticity.ci_lower:.3f}, {results.base_elasticity.ci_upper:.3f}]")

    if results.promo_elasticity is not None:
        print(f"\nPromotional Elasticity:")
        print(f"  Mean: {results.promo_elasticity.mean:.3f}")
        print(f"  Median: {results.promo_elasticity.median:.3f}")
        print(f"  95% CI: [{results.promo_elasticity.ci_lower:.3f}, {results.promo_elasticity.ci_upper:.3f}]")

    # Probability statements (KEY BAYESIAN ADVANTAGE!)
    print(f"\nProbability Statements:")
    prob1 = results.probability('base_elasticity < -2.0')
    print(f"  P(base_elasticity < -2.0) = {prob1:.1%}")

    if results.promo_elasticity is not None:
        prob2 = results.probability('promo_elasticity < -3.0')
        print(f"  P(promo_elasticity < -3.0) = {prob2:.1%}")

    # ============================================================================
    # STEP 5: REVENUE SCENARIOS
    # ============================================================================

    print("\n" + "="*80)
    print("REVENUE IMPACT SCENARIOS (BASE vs PROMO)")
    print("="*80)

    # Base price scenarios
    price_changes = [-5, -3, -1, 1, 3, 5]
    print(f"\nBASE PRICE CHANGES")
    print(f"{'Price Change':<15} {'Revenue Impact':<20} {'P(Positive)':<15}")
    print("-"*55)
    for change in price_changes:
        impact = results.base_price_impact(change)
        print(f"{change:+d}%             "
              f"{impact['revenue_impact_mean']:+.1f}%              "
              f"{impact['probability_positive']:.1%}")

    # Promo scenarios
    if results.promo_elasticity is not None:
        discounts = [5, 10, 15, 20]
        print(f"\nPROMOTIONAL DISCOUNTS")
        print(f"{'Discount':<15} {'Revenue Impact':<20} {'P(Positive)':<15}")
        print("-"*55)
        for d in discounts:
            impact = results.promo_impact(d)
            print(f"{d:>2.0f}% off          "
                  f"{impact['revenue_impact_mean']:+.1f}%              "
                  f"{impact['probability_positive']:.1%}")

    # ============================================================================
    # STEP 6: GENERATE REPORTS
    # ============================================================================

    print("\n" + "="*80)
    print("GENERATING REPORTS")
    print("="*80)

    report_paths = generate_html_report(
        results=results,
        data=df,
        output_dir='./output_example_01',
    )

    print(f"\n✓ Reports generated:")
    for k, v in report_paths.items():
        print(f"  - {k}: {v}")

    # ============================================================================
    # STEP 7: KEY TAKEAWAYS
    # ============================================================================

    print("\n" + "="*80)
    print("KEY TAKEAWAYS")
    print("="*80)

    elasticity = results.base_elasticity.mean

    if abs(elasticity) > 1:
        print(f"\n✓ Demand is ELASTIC (|elasticity| = {abs(elasticity):.2f} > 1)")
        print(f"  → Price increases HURT revenue")
        print(f"  → Price decreases BOOST revenue")
        print(f"\nRecommendation:")
        print(f"  Consider small price reductions (2-3%) to boost revenue")
    else:
        print(f"\n✓ Demand is INELASTIC (|elasticity| = {abs(elasticity):.2f} < 1)")
        print(f"  → Price increases BOOST revenue")
        print(f"  → Price decreases HURT revenue")
        print(f"\nRecommendation:")
        print(f"  Consider small price increases (2-3%) to boost revenue")

    print("\n" + "="*80)
    print("✓ EXAMPLE 1 COMPLETE")
    print("="*80)


if __name__ == "__main__":
    main()
