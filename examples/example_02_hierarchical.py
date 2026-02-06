"""
Example 2: Hierarchical Bayesian Model (Circana / homogeneous schema)

This example demonstrates (V2):
- Hierarchical modeling with partial pooling
- Group-specific base AND promotional elasticity estimates
- Comparing retailers statistically
- Benefits of borrowing strength across groups

Use this when:
- Analyzing multiple Circana-style retailers with the same schema (e.g., BJ's + Sam's Club)
- Want more stable group-specific estimates
- Some groups have limited data
- Want to quantify between-group variation

Note:
- This example intentionally loads **only** `data/bjs.csv` and `data/sams.csv`.
- For a hierarchical run that includes Costco CRX (heterogeneous schema + masking), see `examples/example_04_costco.py`.
"""

import sys
from pathlib import Path

# Allow running this file directly: `python examples/example_02_hierarchical.py`
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data_prep import ElasticityDataPrep, PrepConfig
from bayesian_models import HierarchicalBayesianModel
from visualizations import generate_html_report

def main():
    # ============================================================================
    # STEP 1: DATA PREPARATION (KEEP RETAILERS SEPARATE)
    # ============================================================================

    print("="*80)
    print("EXAMPLE 2: HIERARCHICAL BAYESIAN MODEL")
    print("="*80)

    # Configure data preparation
    # KEY: Use 'All' to keep retailers separate (required for hierarchical)
    prep_config = PrepConfig(
        retailer_filter='All',  # Keep retailers separate!
        include_seasonality=True,
        include_promotions=True,
        separate_base_promo=True,  # V2: dual elasticity (default-on)
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
    print(f"Retailers: {df['Retailer'].unique().tolist()}")

    # Show observations per retailer
    print(f"\nObservations per retailer:")
    for retailer in df['Retailer'].unique():
        n_obs = len(df[df['Retailer'] == retailer])
        print(f"  {retailer}: {n_obs}")

    # ============================================================================
    # STEP 2: FIT HIERARCHICAL MODEL
    # ============================================================================

    print("\n" + "="*80)
    print("FITTING HIERARCHICAL BAYESIAN MODEL")
    print("="*80)

    # Create hierarchical model
    model = HierarchicalBayesianModel(
        priors='default',      # Use weakly informative priors
        n_samples=2000,        # Number of posterior samples
        n_chains=4,            # Number of MCMC chains
        n_tune=1000,           # Tuning/burn-in steps
        random_seed=42,
        verbose=True
    )

    # Fit model
    # The model will automatically:
    # - Estimate global (population) elasticity
    # - Estimate group-specific elasticities
    # - Apply partial pooling (shrinkage toward global mean)
    results = model.fit(df)

    # ============================================================================
    # STEP 3: VIEW RESULTS
    # ============================================================================

    print("\n" + "="*80)
    print("HIERARCHICAL MODEL RESULTS")
    print("="*80)

    # Print full summary
    print(results.summary())

    # ============================================================================
    # STEP 4: GLOBAL VS GROUP-SPECIFIC ESTIMATES
    # ============================================================================

    print("\n" + "="*80)
    print("GLOBAL VS GROUP-SPECIFIC ESTIMATES")
    print("="*80)

    # Global (population) estimate
    print(f"\n📊 Global Base Elasticity (across all retailers):")
    print(f"  Mean: {results.global_base_elasticity.mean:.3f}")
    print(f"  95% CI: [{results.global_base_elasticity.ci_lower:.3f}, {results.global_base_elasticity.ci_upper:.3f}]")

    print(f"\n📊 Global Promotional Elasticity (across all retailers):")
    print(f"  Mean: {results.global_promo_elasticity.mean:.3f}")
    print(f"  95% CI: [{results.global_promo_elasticity.ci_lower:.3f}, {results.global_promo_elasticity.ci_upper:.3f}]")

    # Between-group variance
    print(f"\n📈 Between-Retailer Variation (Base):")
    print(f"  σ_group_base = {results.sigma_group_base.mean:.3f}")
    if results.sigma_group_base.mean < 0.15:
        print(f"  → Retailers are VERY SIMILAR")
    elif results.sigma_group_base.mean < 0.3:
        print(f"  → Retailers have MODERATE variation")
    else:
        print(f"  → Retailers DIFFER SUBSTANTIALLY")

    # Group-specific estimates
    print(f"\n🏪 Retailer-Specific Elasticities:")
    for retailer in results.groups:
        elasticity = results.group_base_elasticities[retailer]
        promo = results.group_promo_elasticities[retailer]
        print(f"\n  {retailer}:")
        print(f"    Base:  {elasticity.mean:.3f} [{elasticity.ci_lower:.3f}, {elasticity.ci_upper:.3f}]")
        print(f"    Promo: {promo.mean:.3f} [{promo.ci_lower:.3f}, {promo.ci_upper:.3f}]")
        
        # Compare to global
        diff = elasticity.mean - results.global_base_elasticity.mean
        if abs(diff) < 0.1:
            print(f"    Similar to global mean")
        elif diff < 0:
            print(f"    MORE elastic than global (by {abs(diff):.3f})")
        else:
            print(f"    LESS elastic than global (by {diff:.3f})")

    # ============================================================================
    # STEP 5: STATISTICAL COMPARISONS
    # ============================================================================

    print("\n" + "="*80)
    print("RETAILER COMPARISONS")
    print("="*80)

    # Compare BJ's vs Sam's (base + promo)
    comparison_base = results.compare_groups("BJ's", "Sam's Club", elasticity_type='base')
    comparison_promo = results.compare_groups("BJ's", "Sam's Club", elasticity_type='promo')

    print(f"\n🔍 BJ's vs Sam's Club (BASE):")
    print(f"  Difference in elasticity: {comparison_base['difference_mean']:.3f}")
    print(f"  95% CI of difference: [{comparison_base['difference_ci'][0]:.3f}, {comparison_base['difference_ci'][1]:.3f}]")
    print(f"  P(BJ's MORE elastic than Sam's) = {comparison_base['probability']:.1%}")

    print(f"\n🔍 BJ's vs Sam's Club (PROMO):")
    print(f"  Difference in elasticity: {comparison_promo['difference_mean']:.3f}")
    print(f"  95% CI of difference: [{comparison_promo['difference_ci'][0]:.3f}, {comparison_promo['difference_ci'][1]:.3f}]")
    print(f"  P(BJ's MORE elastic than Sam's) = {comparison_promo['probability']:.1%}")

    if comparison_base['probability'] > 0.95:
        print(f"\n  → BJ's is definitively MORE price sensitive")
    elif comparison_base['probability'] < 0.05:
        print(f"\n  → Sam's is definitively MORE price sensitive")
    elif comparison_base['probability'] > 0.8:
        print(f"\n  → BJ's is probably MORE price sensitive")
    elif comparison_base['probability'] < 0.2:
        print(f"\n  → Sam's is probably MORE price sensitive")
    else:
        print(f"\n  → Retailers have SIMILAR price sensitivity")

    # ============================================================================
    # STEP 6: UNDERSTAND PARTIAL POOLING
    # ============================================================================

    print("\n" + "="*80)
    print("UNDERSTANDING PARTIAL POOLING")
    print("="*80)

    print(f"""
Hierarchical models use "partial pooling" - each retailer's estimate
is a balance between:
1. Its own data
2. The overall (global) pattern

This is beneficial because:
- Stabilizes estimates when sample size is small
- Prevents extreme estimates from noise
- Quantifies between-group variation
- Allows predicting for new groups

Example:
  If BJ's shows elasticity of -2.0 but has limited data,
  and Sam's shows -2.3 with similar data,
  the model will "shrink" both toward the global mean (~-2.15)
  The amount of shrinkage depends on:
  - Sample size (smaller → more shrinkage)
  - Between-group variance (larger → less shrinkage)
""")

    # ============================================================================
    # STEP 7: RETAILER-SPECIFIC RECOMMENDATIONS
    # ============================================================================

    print("\n" + "="*80)
    print("RETAILER-SPECIFIC RECOMMENDATIONS")
    print("="*80)

    for retailer, elasticity in results.group_elasticities.items():
        print(f"\n🏪 {retailer}:")
        print(f"  Elasticity: {elasticity.mean:.3f}")
        
        if abs(elasticity.mean) > 2.2:
            print(f"  → HIGHLY elastic - be very cautious with price increases")
            print(f"  → Even small increases (1-2%) could hurt revenue")
            print(f"  → Consider 2-3% price reductions to boost revenue")
        elif abs(elasticity.mean) > 2.0:
            print(f"  → Moderately elastic - some pricing flexibility")
            print(f"  → Avoid increases >2%")
            print(f"  → Small reductions (2%) could boost revenue")
        else:
            print(f"  → Less elastic - more pricing power")
            print(f"  → Can consider small price increases")

    # ============================================================================
    # STEP 8: GENERATE REPORTS
    # ============================================================================

    print("\n" + "="*80)
    print("GENERATING REPORTS")
    print("="*80)

    # Generate complete HTML report
    # This will include group comparison plots
    report_path = generate_html_report(
        results=results,
        data=df,
        output_dir='./output_example_02',
        report_name='hierarchical_model_report.html'
    )

    print(f"\n✓ Complete HTML report generated!")
    print(f"  Location: {report_path}")
    print(f"  Includes group comparison plots")

    # ============================================================================
    # STEP 9: KEY TAKEAWAYS
    # ============================================================================

    print("\n" + "="*80)
    print("KEY TAKEAWAYS FROM HIERARCHICAL MODEL")
    print("="*80)

    print(f"""
✓ Global Insights:
  - Overall elasticity: {results.global_elasticity.mean:.3f}
  - Between-retailer variation: {results.sigma_group.mean:.3f}

✓ Retailer Differences:
  - Estimates are more stable than separate models
  - Can quantify which retailers are more/less elastic
  - Uncertainty properly reflects both data and pooling

✓ Advantages Over Simple Model:
  - More accurate when sample sizes differ
  - Automatic regularization (prevents overfitting)
  - Can predict for new retailers
  - Quantifies group variation

✓ When to Use Hierarchical:
  - Multiple groups (retailers, regions, stores)
  - Some groups have limited data
  - Want to borrow strength across groups
  - Planning to add more groups later
""")

    print("\n" + "="*80)
    print("✓ EXAMPLE 2 COMPLETE")
    print("="*80)


if __name__ == "__main__":
    main()
