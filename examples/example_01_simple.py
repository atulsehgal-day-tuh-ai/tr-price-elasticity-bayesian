"""
Example 1: Simple Bayesian Model - Basic Usage

This example demonstrates:
- Basic data preparation
- Fitting a simple (non-hierarchical) Bayesian model
- Viewing results
- Probability statements
- Revenue scenarios

Use this when:
- Analyzing overall data (BJ's + Sam's combined)
- Single retailer analysis
- Getting started with the system
"""

from data_prep import ElasticityDataPrep, PrepConfig
from bayesian_models import SimpleBayesianModel
from visualizations import generate_html_report

# ============================================================================
# STEP 1: DATA PREPARATION
# ============================================================================

print("="*80)
print("EXAMPLE 1: SIMPLE BAYESIAN MODEL")
print("="*80)

# Configure data preparation
# Use 'Overall' to combine BJ's and Sam's into one dataset
prep_config = PrepConfig(
    retailer_filter='Overall',  # Combine retailers
    include_seasonality=True,
    include_promotions=True,
    verbose=True
)

# Initialize prep
prep = ElasticityDataPrep(prep_config)

# Transform data
# NOTE: Update these paths to your actual data files
df = prep.transform(
    bjs_path='path/to/bjs.csv',
    sams_path='path/to/sams.csv'
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
print(f"\nOwn-Price Elasticity:")
print(f"  Mean: {results.elasticity_own.mean:.3f}")
print(f"  Median: {results.elasticity_own.median:.3f}")
print(f"  95% CI: [{results.elasticity_own.ci_lower:.3f}, {results.elasticity_own.ci_upper:.3f}]")

# Probability statements (KEY BAYESIAN ADVANTAGE!)
print(f"\nProbability Statements:")
prob1 = results.probability('elasticity_own < -2.0')
print(f"  P(elasticity < -2.0) = {prob1:.1%}")

prob2 = results.probability('elasticity_own < -2.5')
print(f"  P(elasticity < -2.5) = {prob2:.1%}")

prob3 = results.probability('elasticity_own > -1.8')
print(f"  P(elasticity > -1.8) = {prob3:.1%}")

# ============================================================================
# STEP 5: REVENUE SCENARIOS
# ============================================================================

print("\n" + "="*80)
print("REVENUE IMPACT SCENARIOS")
print("="*80)

# Test different price changes
price_changes = [-5, -3, -1, 1, 3, 5]

print(f"\n{'Price Change':<15} {'Revenue Impact':<20} {'P(Positive)':<15}")
print("-"*50)

for change in price_changes:
    impact = results.revenue_impact(change)
    print(f"{change:+d}%             "
          f"{impact['revenue_impact_mean']:+.1f}%              "
          f"{impact['probability_positive']:.1%}")

# Detailed scenario
print(f"\n📊 Detailed Analysis: 3% Price Reduction")
impact_3pct = results.revenue_impact(-3)
print(f"  Price Change: -3%")
print(f"  Expected Volume Change: {impact_3pct['volume_impact_mean']:+.1f}%")
print(f"  Expected Revenue Change: {impact_3pct['revenue_impact_mean']:+.1f}%")
print(f"  95% CI: [{impact_3pct['revenue_impact_ci'][0]:+.1f}%, {impact_3pct['revenue_impact_ci'][1]:+.1f}%]")
print(f"  Probability of Revenue Increase: {impact_3pct['probability_positive']:.1%}")

# ============================================================================
# STEP 6: GENERATE REPORTS
# ============================================================================

print("\n" + "="*80)
print("GENERATING REPORTS")
print("="*80)

# Generate complete HTML report with all visualizations
report_path = generate_html_report(
    results=results,
    data=df,
    output_dir='./output_example_01',
    report_name='simple_model_report.html'
)

print(f"\n✓ Complete HTML report generated!")
print(f"  Location: {report_path}")
print(f"  Open in browser to view all plots and results")

# ============================================================================
# STEP 7: KEY TAKEAWAYS
# ============================================================================

print("\n" + "="*80)
print("KEY TAKEAWAYS")
print("="*80)

elasticity = results.elasticity_own.mean

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
