"""
Example 5: Dual Elasticity Showcase (Base vs Promotional)

This example demonstrates:
- V2 data prep: base price extraction + promo depth calculation
- Fitting the V2 simple model with two elasticities:
  - base_elasticity (strategic, permanent price changes)
  - promo_elasticity (tactical, temporary discounts)
- Comparing base vs promo responsiveness
- Running separate revenue scenarios for base price changes vs promotions
"""

import sys
from pathlib import Path

# Allow running this file directly: `python examples/example_05_base_vs_promo.py`
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data_prep import ElasticityDataPrep, PrepConfig
from bayesian_models import SimpleBayesianModel
from visualizations import generate_html_report


def main():
    print("=" * 80)
    print("EXAMPLE 5: BASE vs PROMO DUAL ELASTICITY")
    print("=" * 80)

    # ------------------------------------------------------------------------
    # STEP 1: DATA PREP (V2)
    # ------------------------------------------------------------------------
    prep = ElasticityDataPrep(
        PrepConfig(
            retailer_filter="Overall",
            separate_base_promo=True,
            include_seasonality=True,
            include_promotions=True,
            include_time_trend=True,
            verbose=True,
        )
    )

    # NOTE: update these to your actual paths
    df = prep.transform(
        bjs_path="path/to/bjs.csv",
        sams_path="path/to/sams.csv",
    )

    print(f"\nPrepared data: {df.shape[0]} rows × {df.shape[1]} cols")

    # ------------------------------------------------------------------------
    # STEP 2: FIT MODEL (V2)
    # ------------------------------------------------------------------------
    model = SimpleBayesianModel(
        priors="default",
        n_samples=2000,
        n_chains=4,
        n_tune=1000,
        target_accept=0.95,
        random_seed=42,
        verbose=True,
    )

    results = model.fit(df)

    # ------------------------------------------------------------------------
    # STEP 3: INTERPRETATION
    # ------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("DUAL ELASTICITY RESULTS")
    print("=" * 80)
    print(f"\nBase Price Elasticity: {results.base_elasticity}")
    if results.promo_elasticity is not None:
        print(f"Promotional Elasticity: {results.promo_elasticity}")

        comp = results.compare_elasticities()
        print(
            f"\n|Promo| / |Base| multiplier: {comp['multiplier_mean']:.2f} "
            f"[{comp['multiplier_ci'][0]:.2f}, {comp['multiplier_ci'][1]:.2f}]"
        )
        print(f"P(|promo| > |base|) = {comp['probability_promo_more_responsive']:.1%}")

    # ------------------------------------------------------------------------
    # STEP 4: SCENARIOS
    # ------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("SCENARIOS")
    print("=" * 80)

    base_impact = results.base_price_impact(price_change_pct=5)
    print(
        f"\nBase +5% → revenue impact: {base_impact['revenue_impact_mean']:+.1f}% "
        f"(P>0: {base_impact['probability_positive']:.0%})"
    )

    if results.promo_elasticity is not None:
        promo_impact = results.promo_impact(discount_depth_pct=10)
        print(
            f"Promo 10% off → revenue impact: {promo_impact['revenue_impact_mean']:+.1f}% "
            f"(P>0: {promo_impact['probability_positive']:.0%})"
        )

    # ------------------------------------------------------------------------
    # STEP 5: REPORT
    # ------------------------------------------------------------------------
    report_path = generate_html_report(
        results=results,
        data=df,
        output_dir="./output_example_05",
        report_name="dual_elasticity_report.html",
    )

    print(f"\n✓ HTML report generated: {report_path}")


if __name__ == "__main__":
    main()

