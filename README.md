# Price Elasticity Bayesian Analysis System

A complete, production-ready system for Bayesian price elasticity analysis with hierarchical modeling, uncertainty quantification, and comprehensive visualizations.

## 🎯 Features

- **Data Transformation**: Automated pipeline from raw Circana data to model-ready format
- **Bayesian Modeling (V2)**: Simple and hierarchical models with **dual elasticities** (base vs promo)
- **Base vs Promo Separation (V2)**: Separates strategic (base price) impact from tactical (promotional discount) impact
- **Hierarchical Support**: Multi-retailer analysis with automatic shrinkage
- **Flexible Priors**: Default (weakly informative), informative, vague, or custom
- **Missing Data Handling**: Automatically handles retailers with missing features (e.g., Costco without promo data)
- **Feature Engineering**: Easy-to-use methods for creating custom features
- **Comprehensive Visualizations**: Trace plots, posterior distributions, seasonal patterns, revenue scenarios
- **HTML Reports**: Complete interactive reports with all analyses
- **Uncertainty Quantification**: Full posterior distributions and probability statements

## 📋 Requirements

- Python 3.8+
- PyMC 5.10+
- See `requirements.txt` for full list

## 🚀 Quick Start

### Installation

```bash
# Install dependencies
pip install -r requirements.txt
```

### Simple Usage

```python
from data_prep import ElasticityDataPrep
from bayesian_models import HierarchicalBayesianModel
from visualizations import generate_html_report

# 1. Prepare data
prep = ElasticityDataPrep()
df = prep.transform('bjs.csv', 'sams.csv')

# 2. Fit Bayesian model
model = HierarchicalBayesianModel()
results = model.fit(df)

# 3. Generate report
generate_html_report(results, output_dir='./output')
```

### Input data requirement (V2)

For best results in **V2 dual-elasticity mode**, your Circana CSVs should include:
- Total sales columns: `Dollar Sales`, `Unit Sales`
- Base sales columns: `Base Dollar Sales`, `Base Unit Sales`

If base sales columns are missing or undefined for some weeks, the system will **estimate/impute** a base price from observed average prices (with warnings if heavy imputation is needed).

### Command Line

```bash
# Run complete analysis
python run_analysis.py --bjs bjs.csv --sams sams.csv --output ./results

# With custom configuration
python run_analysis.py --config my_config.yaml
```

## 📖 Documentation

### Architecture (how it all connects)

See **`architecture.md`** for a detailed architecture diagram, module responsibilities, call graphs, and the end-to-end data/model/report flow.

### Notebook walkthrough (recommended for first run)

If you want to build confidence in the **data transformation** step-by-step before fitting models, start with:

- `notebooks/01_data_transformation_exploration.ipynb`

It runs `ElasticityDataPrep.transform(...)`, shows interim sanity checks (columns, distributions, missingness, retailer breakdown), makes a few quick plots, and exports a `prepared_data_from_notebook.csv` for auditing.

### Data Preparation

```python
from data_prep import ElasticityDataPrep, PrepConfig

# Basic usage
prep = ElasticityDataPrep(
    PrepConfig(
        retailer_filter='All',  # 'All', 'Overall', 'BJs', 'Sams', 'Costco'
        include_seasonality=True,
        include_promotions=True
    )
)

df = prep.transform(
    bjs_path='bjs.csv',
    sams_path='sams.csv'
)
```

#### Adding Custom Features

```python
# Interaction terms
df = prep.add_interaction_term(df, 'log_price_si', 'spring')

# Lagged features
df = prep.add_lagged_feature(df, 'log_price_si', lags=[1, 2, 4])

# Moving averages
df = prep.add_moving_average(df, 'price_si', windows=[4, 8, 12])

# Custom formula
df = prep.add_custom_feature(
    df,
    name='price_gap',
    formula=lambda x: x['price_si'] - x['price_pl']
)
```

#### Handling Missing Features (Costco Example)

```python
prep = ElasticityDataPrep(
    retailers={
        'BJs': {'has_promo': True, 'has_competitor': True},
        'Sams': {'has_promo': True, 'has_competitor': True},
        'Costco': {'has_promo': False, 'has_competitor': True}  # Missing promo!
    }
)

df = prep.transform('bjs.csv', 'sams.csv', 'costco.csv')
```

### Bayesian Modeling

```python
from bayesian_models import HierarchicalBayesianModel

model = HierarchicalBayesianModel(
    priors='default',    # 'default', 'informative', 'vague'
    n_samples=2000,
    n_chains=4,
    n_tune=1000,
    target_accept=0.95
)
results = model.fit(df)

# Access results
print(f"Global elasticity: {results.global_elasticity.mean:.3f}")
print(f"BJ's elasticity: {results.group_elasticities[\"BJ's\"].mean:.3f}")
```

In V2 dual-elasticity mode, you also get:

```python
print(f"Base price elasticity: {results.base_elasticity.mean:.3f}")
print(f"Promo elasticity: {results.promo_elasticity.mean:.3f}")
```

### Probability Statements

```python
# Direct probability statements
prob = results.probability('elasticity_own < -2.0')
print(f"P(elasticity < -2.0) = {prob:.1%}")

# Revenue impact
impact = results.revenue_impact(price_change_pct=-3)
print(f"3% price cut: {impact['revenue_impact_mean']:+.1f}% revenue impact")
```

V2 also supports separate scenario helpers:

```python
base_impact = results.base_price_impact(price_change_pct=5)
promo_impact = results.promo_impact(discount_depth_pct=10)
print(base_impact, promo_impact)
```

## 📂 Project Structure

```
price_elasticity_bayesian/
├── README.md
├── requirements.txt
├── config_template.yaml
├── data_prep.py
├── bayesian_models.py
├── visualizations.py
├── run_analysis.py
└── examples/
    ├── example_01_simple.py
    ├── example_02_hierarchical.py
    ├── example_03_add_features.py
    └── example_04_costco.py
```

## 🎓 Examples

See `examples/` directory for complete examples:
- Simple model
- Hierarchical model
- Custom features
- Missing data handling

## 📊 HTML Report Contents

1. Executive Summary
2. Trace Plots (MCMC diagnostics)
3. Posterior Distributions
4. Seasonal Analysis
5. Revenue Scenarios
6. Model Comparisons
7. Group Comparisons (hierarchical)

## 🐛 Troubleshooting

### Convergence Issues
```python
config = ModelConfig(n_tune=2000, target_accept=0.99)
```

### Slow Sampling
```python
config = ModelConfig(n_samples=500, n_chains=2)  # For testing
```

---

**Version**: 1.0.0  
**Last Updated**: February 2026
