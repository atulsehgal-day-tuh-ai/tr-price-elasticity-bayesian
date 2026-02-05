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

# ============================================================================
# STEP 1: CONFIGURE RETAILER-SPECIFIC SETTINGS
# ============================================================================

print("="*80)
print("EXAMPLE 4: ADDING COSTCO WITH MISSING DATA")
print("="*80)

print("""
Scenario:
--------
You have data for BJ's, Sam's, and Costco, but:
- BJ's: Full data (sales, price, promo, competitor)
- Sam's: Full data (sales, price, promo, competitor)
- Costco: Partial data (sales, price, competitor, but NO promo)

The system will automatically handle this!
""")

# Configure retailer-specific settings
retailer_config = {
    'BJs': {
        'has_promo': True,        # BJ's has promotional data
        'has_competitor': True     # BJ's has competitor price data
    },
    'Sams': {
        'has_promo': True,        # Sam's has promotional data
        'has_competitor': True     # Sam's has competitor price data
    },
    'Costco': {
        'has_promo': False,       # ⚠️ Costco MISSING promotional data
        'has_competitor': True     # Costco has competitor price data
    }
}

# ============================================================================
# STEP 2: DATA PREPARATION WITH MISSING DATA HANDLING
# ============================================================================

print("\n" + "="*80)
print("DATA PREPARATION (WITH MISSING DATA HANDLING)")
print("="*80)

# Configure data prep with retailer settings
prep_config = PrepConfig(
    retailer_filter='All',         # Keep all retailers separate
    include_seasonality=True,
    include_promotions=True,       # Will be included for BJ's/Sam's only
    separate_base_promo=True,      # V2: dual elasticity (default-on)
    retailers=retailer_config,     # Pass retailer-specific config
    verbose=True
)

# Initialize prep
prep = ElasticityDataPrep(prep_config)

# Transform data - NOTE: Include Costco path
# NOTE: Update these paths to your actual data files
df = prep.transform(
    bjs_path='path/to/bjs.csv',
    sams_path='path/to/sams.csv',
    costco_path='path/to/costco.csv'  # Add Costco!
)

print(f"\nData prepared: {len(df)} observations")
print(f"Retailers: {df['Retailer'].unique().tolist()}")

# Show observations per retailer
print(f"\nObservations per retailer:")
for retailer in df['Retailer'].unique():
    n_obs = len(df[df['Retailer'] == retailer])
    print(f"  {retailer}: {n_obs}")

# ============================================================================
# STEP 3: INSPECT DATA AVAILABILITY
# ============================================================================

print("\n" + "="*80)
print("DATA AVAILABILITY CHECK")
print("="*80)

# Check which retailers have which features
if 'has_promo' in df.columns:
    print(f"\nPromotional Data Availability:")
    for retailer in df['Retailer'].unique():
        has_promo = df[df['Retailer'] == retailer]['has_promo'].iloc[0]
        print(f"  {retailer}: {'✓ Available' if has_promo == 1 else '✗ Missing'}")

# Show sample data
print(f"\nSample Data (showing promo availability):")
sample_cols = ['Date', 'Retailer', 'Log_Price_SI', 'Promo_Intensity_SI', 'has_promo']
if all(col in df.columns for col in sample_cols):
    print(df[sample_cols].groupby('Retailer').head(3))

# ============================================================================
# STEP 4: FIT HIERARCHICAL MODEL
# ============================================================================

print("\n" + "="*80)
print("FITTING HIERARCHICAL MODEL (3 RETAILERS)")
print("="*80)

print("""
The hierarchical model will:
1. Estimate global elasticity across all 3 retailers
2. Estimate retailer-specific elasticities (with partial pooling)
3. Include promo effect for BJ's and Sam's only
4. Exclude promo effect for Costco (automatically handled)
5. Still pool elasticity across all 3 retailers
""")

# Create hierarchical model
model = HierarchicalBayesianModel(
    priors='default',
    n_samples=2000,
    n_chains=4,
    n_tune=1000,
    random_seed=42,
    verbose=True
)

# Fit model
# Model automatically adjusts for missing features
results = model.fit(df)

# ============================================================================
# STEP 5: VIEW RESULTS (3 RETAILERS)
# ============================================================================

print("\n" + "="*80)
print("RESULTS WITH 3 RETAILERS")
print("="*80)

# Global estimate
print(f"\n📊 Global Elasticity (across all 3 retailers):")
print(f"  Mean: {results.global_elasticity.mean:.3f}")
print(f"  95% CI: [{results.global_elasticity.ci_lower:.3f}, {results.global_elasticity.ci_upper:.3f}]")

# Between-retailer variance
print(f"\n📈 Between-Retailer Variation:")
print(f"  σ_group = {results.sigma_group.mean:.3f}")

# All retailer-specific estimates
print(f"\n🏪 Retailer-Specific Elasticities (Base + Promo):")
for retailer in results.groups:
    base_e = results.group_base_elasticities[retailer]
    promo_e = results.group_promo_elasticities[retailer]
    print(f"\n  {retailer}:")
    print(f"    Base:  {base_e.mean:.3f} [{base_e.ci_lower:.3f}, {base_e.ci_upper:.3f}]")
    print(f"    Promo: {promo_e.mean:.3f} [{promo_e.ci_lower:.3f}, {promo_e.ci_upper:.3f}]")
    
    if retailer == 'Costco':
        print(f"    ⚠️ Note: Costco has no promo feature in data (has_promo=0)")
        print(f"    → Promo elasticity is prior-informed via hierarchical pooling")
        print(f"    → Base elasticity still uses Costco's own price variation + pooling")

# ============================================================================
# STEP 6: COMPARE ALL THREE RETAILERS
# ============================================================================

print("\n" + "="*80)
print("THREE-WAY COMPARISON")
print("="*80)

# Compare each pair
retailer_pairs = [
    ("BJ's", "Sam's Club"),
    ("BJ's", "Costco"),
    ("Sam's Club", "Costco")
]

for retailer1, retailer2 in retailer_pairs:
    comparison_base = results.compare_groups(retailer1, retailer2, elasticity_type='base')
    comparison_promo = results.compare_groups(retailer1, retailer2, elasticity_type='promo')
    print(f"\n🔍 {retailer1} vs {retailer2}:")
    print(f"  Base diff:  {comparison_base['difference_mean']:.3f} | P({retailer1} more elastic on base) = {comparison_base['probability']:.1%}")
    print(f"  Promo diff: {comparison_promo['difference_mean']:.3f} | P({retailer1} more elastic on promo) = {comparison_promo['probability']:.1%}")

# ============================================================================
# STEP 7: UNDERSTAND THE BENEFITS
# ============================================================================

print("\n" + "="*80)
print("BENEFITS OF THIS APPROACH")
print("="*80)

print(f"""
✓ What the system did automatically:

1. Data Preparation:
   - Loaded all 3 retailers
   - Marked Costco's promo data as missing (NaN)
   - Added 'has_promo' indicator column
   - Kept all other features intact

2. Model Building:
   - Included promo effect for BJ's & Sam's
   - Excluded promo effect for Costco
   - Still pooled elasticity across all 3
   - Properly handled uncertainty

3. Results:
   - Costco elasticity is estimated from:
     * Its own price/sales data
     * Borrowing strength from BJ's/Sam's
     * Without bias from missing promo

✓ Why this is better than alternatives:

❌ Don't exclude Costco entirely:
   - Wastes valuable data
   - Can't make Costco-specific decisions
   - Loses opportunity for pooling

❌ Don't impute promo with zeros:
   - Creates false patterns
   - Biases elasticity estimates
   - Mixes promotional and non-promotional effects

✓ Do use hierarchical model with missing data:
   - Uses all available information
   - Properly quantifies uncertainty
   - Borrows strength appropriately
   - Unbiased estimates

✓ Additional benefits:
   - Easy to add more retailers later
   - Handles different data structures
   - Extensible to other missing features
   - Principled uncertainty quantification
""")

# ============================================================================
# STEP 8: COSTCO-SPECIFIC INSIGHTS
# ============================================================================

print("\n" + "="*80)
print("COSTCO-SPECIFIC INSIGHTS")
print("="*80)

costco_elasticity = results.group_elasticities['Costco']

print(f"\n🏪 Costco Analysis:")
print(f"  Elasticity: {costco_elasticity.mean:.3f}")
print(f"  95% CI: [{costco_elasticity.ci_lower:.3f}, {costco_elasticity.ci_upper:.3f}]")

# Compare uncertainty to BJ's/Sam's
bjs_std = results.group_elasticities["BJ's"].std
costco_std = costco_elasticity.std

print(f"\n  Uncertainty comparison:")
print(f"    BJ's std: {bjs_std:.3f}")
print(f"    Costco std: {costco_std:.3f}")

if costco_std > bjs_std * 1.2:
    print(f"    → Costco has MORE uncertainty (expected due to missing promo)")
else:
    print(f"    → Uncertainties are similar (pooling helps!)")

print(f"""
💡 Implications for Costco:
  - Can make pricing decisions despite missing promo data
  - Elasticity estimate benefits from BJ's/Sam's patterns
  - Uncertainty properly reflects data limitations
  - Future: If promo data becomes available, can update model
""")

# ============================================================================
# STEP 9: GENERATE REPORTS
# ============================================================================

print("\n" + "="*80)
print("GENERATING REPORTS")
print("="*80)

# Generate HTML report with 3-retailer comparison
report_path = generate_html_report(
    results=results,
    data=df,
    output_dir='./output_example_04',
    report_name='three_retailer_report.html'
)

print(f"\n✓ Complete HTML report generated!")
print(f"  Location: {report_path}")
print(f"  Includes 3-retailer comparison plots")

# ============================================================================
# STEP 10: KEY TAKEAWAYS
# ============================================================================

print("\n" + "="*80)
print("KEY TAKEAWAYS")
print("="*80)

print(f"""
✓ Handling Missing Data:
  - Configure retailer-specific settings
  - System automatically adjusts model
  - No manual data manipulation needed
  - Proper uncertainty quantification

✓ Three-Retailer Insights:
  - Global elasticity: {results.global_elasticity.mean:.3f}
  - All retailers inform each other
  - Can compare any pair statistically
  - Quantified between-retailer variation

✓ Future Extensions:
  - Easy to add 4th, 5th retailer
  - Can handle other missing features
  - Can mix different data time periods
  - Flexible and extensible

✓ Best Practices:
  - Always specify what's missing explicitly
  - Don't impute unless theoretically justified
  - Use hierarchical model for stability
  - Check uncertainty differences

⚠️ Warnings:
  - More missing data → more uncertainty
  - Can't estimate effects of missing features
  - Need sufficient data in each group
  - Validate assumptions about missingness
""")

print("\n" + "="*80)
print("✓ EXAMPLE 4 COMPLETE")
print("="*80)

print(f"""
You now know how to:
✓ Add retailers with incomplete data
✓ Configure retailer-specific settings
✓ Fit hierarchical models with missing features
✓ Interpret results with missing data
✓ Make decisions despite data limitations

Ready for production use! 🚀
""")
