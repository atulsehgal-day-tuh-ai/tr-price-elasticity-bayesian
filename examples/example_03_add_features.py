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
from visualizations import generate_html_report
import pandas as pd
import numpy as np

# ============================================================================
# STEP 1: BASIC DATA PREPARATION
# ============================================================================

print("="*80)
print("EXAMPLE 3: CUSTOM FEATURE ENGINEERING")
print("="*80)

# Prepare data normally first
prep_config = PrepConfig(
    retailer_filter='Overall',
    include_seasonality=True,
    include_promotions=True,
    verbose=True
)

prep = ElasticityDataPrep(prep_config)

# NOTE: Update paths to your actual data
df = prep.transform(
    bjs_path='path/to/bjs.csv',
    sams_path='path/to/sams.csv'
)

print(f"\nBasic data prepared: {len(df)} observations")
print(f"Columns: {df.columns.tolist()}")

# ============================================================================
# STEP 2: ADD INTERACTION TERMS
# ============================================================================

print("\n" + "="*80)
print("ADDING INTERACTION TERMS")
print("="*80)

# Test if price elasticity differs by season
# Interaction: price × spring
df = prep.add_interaction_term(
    df,
    var1='Log_Price_SI',
    var2='Spring',
    name='Price_x_Spring'
)

print(f"\n✓ Added Price_x_Spring interaction")
print(f"  This tests: Does price sensitivity differ in Spring?")

# Can add more interactions
df = prep.add_interaction_term(
    df,
    var1='Log_Price_SI',
    var2='Summer',
    name='Price_x_Summer'
)

print(f"✓ Added Price_x_Summer interaction")

# ============================================================================
# STEP 3: ADD LAGGED FEATURES
# ============================================================================

print("\n" + "="*80)
print("ADDING LAGGED FEATURES")
print("="*80)

# Add lagged prices to test momentum/carryover effects
df = prep.add_lagged_feature(
    df,
    var='Log_Price_SI',
    lags=[1, 4],  # 1-week and 4-week lags
    group_by=None
)

print(f"\n✓ Added lagged prices:")
print(f"  - Log_Price_SI_lag1 (last week's price)")
print(f"  - Log_Price_SI_lag4 (4 weeks ago price)")
print(f"  This tests: Do past prices affect current sales?")

# ============================================================================
# STEP 4: ADD MOVING AVERAGES
# ============================================================================

print("\n" + "="*80)
print("ADDING MOVING AVERAGES")
print("="*80)

# Add moving average for reference price effect
df = prep.add_moving_average(
    df,
    var='Price_SI',  # Use actual price (not log)
    windows=[4, 8],  # 4-week and 8-week moving average
    group_by=None
)

print(f"\n✓ Added moving averages:")
print(f"  - Price_SI_ma4 (4-week average price)")
print(f"  - Price_SI_ma8 (8-week average price)")
print(f"  This enables: Reference price effects (current vs average)")

# ============================================================================
# STEP 5: ADD CUSTOM FEATURES
# ============================================================================

print("\n" + "="*80)
print("ADDING CUSTOM FEATURES")
print("="*80)

# Create price gap (SI price - PL price)
df = prep.add_custom_feature(
    df,
    name='Price_Gap',
    formula=lambda d: d['Price_SI'] - d['Price_PL']
)

print(f"\n✓ Added Price_Gap feature")
print(f"  = SI Price - PL Price")
print(f"  This tests: Does price differential matter?")

# Create price index (current price / 4-week average)
df = prep.add_custom_feature(
    df,
    name='Price_Index',
    formula=lambda d: d['Price_SI'] / d['Price_SI_ma4']
)

print(f"✓ Added Price_Index feature")
print(f"  = Current Price / 4-week Average")
print(f"  This tests: Reference price effects")

# Create log of price gap
df = prep.add_custom_feature(
    df,
    name='Log_Price_Gap',
    formula=lambda d: pd.Series([
        0 if g <= 0 else np.log(g)
        for g in d['Price_Gap']
    ], index=d.index)
)

print(f"✓ Added Log_Price_Gap feature")

# ============================================================================
# STEP 6: INSPECT NEW FEATURES
# ============================================================================

print("\n" + "="*80)
print("INSPECTING NEW FEATURES")
print("="*80)

# Show sample of data with new features
print(f"\nSample of enhanced data:")
feature_cols = [
    'Date', 'Log_Price_SI', 'Price_x_Spring', 
    'Log_Price_SI_lag1', 'Price_SI_ma4', 'Price_Gap'
]
print(df[feature_cols].head(10))

# Summary statistics
print(f"\nSummary of new features:")
new_features = [
    'Price_x_Spring', 'Log_Price_SI_lag1', 
    'Log_Price_SI_lag4', 'Price_SI_ma4', 'Price_Gap'
]
print(df[new_features].describe())

# ============================================================================
# STEP 7: FIT MODEL WITH NEW FEATURES
# ============================================================================

print("\n" + "="*80)
print("FITTING MODEL WITH CUSTOM FEATURES")
print("="*80)

print("""
NOTE: The current SimpleBayesianModel uses a fixed set of features.
To include custom features, you would need to either:

1. Modify the model class to accept additional features
2. Or manually add terms to the PyMC model

For this example, we'll show how you WOULD do it:
""")

# Example of what you'd do (pseudocode):
print(f"""
# In bayesian_models.py, you could extend the model:

class SimpleBayesianModel:
    def __init__(self, custom_features=None, ...):
        self.custom_features = custom_features or []
    
    def _build_model(self, data):
        # ... existing code ...
        
        # Add custom features
        for feature in self.custom_features:
            if feature in data.columns:
                beta = pm.Normal(f'beta_{feature}', mu=0, sigma=0.2)
                mu += beta * data[feature].values

# Then use it:
model = SimpleBayesianModel(
    custom_features=['Price_x_Spring', 'Log_Price_SI_lag1']
)
""")

# For now, fit standard model
print(f"\nFitting standard model with basic features...")
model = SimpleBayesianModel(
    priors='default',
    n_samples=1000,  # Fewer samples for demo
    n_chains=2,
    verbose=True
)

# Drop rows with NaN (from lagging)
df_clean = df.dropna()
print(f"After dropping NaN from lags: {len(df_clean)} rows")

results = model.fit(df_clean)

# ============================================================================
# STEP 8: ANALYZING FEATURE IMPORTANCE
# ============================================================================

print("\n" + "="*80)
print("ANALYZING FEATURE IMPORTANCE")
print("="*80)

# Show correlations with sales
print(f"\nCorrelations with Log Sales:")
correlations = df_clean[[
    'Log_Unit_Sales_SI',
    'Log_Price_SI',
    'Log_Price_SI_lag1',
    'Log_Price_SI_lag4',
    'Price_Gap',
    'Price_Index'
]].corr()['Log_Unit_Sales_SI'].sort_values(ascending=False)

print(correlations)

# ============================================================================
# STEP 9: RECOMMENDATIONS FOR CUSTOM FEATURES
# ============================================================================

print("\n" + "="*80)
print("CUSTOM FEATURE RECOMMENDATIONS")
print("="*80)

print(f"""
✓ Interaction Terms (Price × Season):
  Purpose: Test if elasticity varies by season
  Example: Price_x_Spring tests if Spring has different elasticity
  Interpretation: If coefficient is significant, elasticity differs
  
✓ Lagged Features:
  Purpose: Capture momentum/carryover effects
  Example: Log_Price_SI_lag1 tests if last week's price matters
  Use case: Promotional carryover, inventory effects
  
✓ Moving Averages:
  Purpose: Reference price effects
  Example: Price_SI_ma4 = recent average price
  Use case: Consumers compare to "usual" price
  
✓ Custom Formulas:
  Purpose: Any transformation you need
  Example: Price_Gap = SI Price - PL Price
  Use case: Test differential pricing effects

💡 Best Practices:
  1. Add one feature at a time and test
  2. Check correlations before adding
  3. Be careful with multicollinearity
  4. Start simple, add complexity as needed
  5. Always validate with domain knowledge

⚠️ Warnings:
  - Lagged features reduce sample size
  - Too many features = overfitting
  - Interactions can be hard to interpret
  - Check for missing values after transformations
""")

# ============================================================================
# STEP 10: SAVE ENHANCED DATA
# ============================================================================

print("\n" + "="*80)
print("SAVING ENHANCED DATA")
print("="*80)

# Save data with all features for future use
output_path = './output_example_03/enhanced_data.csv'
df_clean.to_csv(output_path, index=False)
print(f"\n✓ Enhanced data saved to: {output_path}")
print(f"  Contains {len(df_clean.columns)} features")

print("\n" + "="*80)
print("✓ EXAMPLE 3 COMPLETE")
print("="*80)

print(f"""
You now know how to:
✓ Add interaction terms
✓ Add lagged features  
✓ Add moving averages
✓ Add custom features with formulas
✓ Analyze feature correlations

Next steps:
→ Modify bayesian_models.py to accept custom features
→ Test specific hypotheses (e.g., seasonal elasticity)
→ Build more sophisticated models
""")
