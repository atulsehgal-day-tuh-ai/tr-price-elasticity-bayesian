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

### Cloud setup (Cursor + GitHub Codespaces) — 16 cores / 64 GB RAM

This repo supports running in GitHub Codespaces (and connecting from Cursor) via a Dev Container.

- **What we added**: `.devcontainer/devcontainer.json`
- **Why**:
  - **Minimum machine spec** request for faster Bayesian sampling: **16 CPU / 64 GB RAM**
  - Install build tooling (`g++`) so PyTensor can compile native code (avoids the “g++ not detected” warning and improves performance)

#### 1) Dev Container configuration

The config is here:

- `.devcontainer/devcontainer.json`

It sets `hostRequirements` (minimum spec) and uses `postCreateCommand` to install build tools + Python deps.

> Note: `hostRequirements` expresses a **minimum** for Codespaces. It does not force a specific SKU if your account/org doesn’t have access to it.

#### 2) Commit + push (required for Codespaces to see it)

Codespaces builds from what’s in GitHub, so commit and push the `.devcontainer/` folder.

#### 3) Create/open a Codespace and select the machine type

In GitHub Codespaces:

- Open your codespace’s menu (**…**) → **Change machine type** → choose **16-core / 64 GB** (if available) → **Update codespace**.

GitHub docs: see “Changing the machine type for your codespace” in the GitHub Codespaces documentation.

#### 4) If 16-core / 64 GB isn’t available in the dropdown

Common reasons:

- **Org policy restriction** (your organization/admin limited allowed machine types)
- **Account/plan limitation** (larger machine types not enabled for your account/enterprise)
- **Region capacity** (try a different region if you have the option)

If you believe you should have access, open a ticket with GitHub Support and ask to enable larger Codespaces machine types for your account/org.

#### 5) PowerShell note (the error we hit)

If you try to create `devcontainer.json` from **PowerShell**, bash-style heredocs like:

- `cat > file << 'EOF'`

will fail with a parser error. Use `Set-Content` / a here-string in PowerShell, or just edit the file directly in the editor (recommended).

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

### Why we prefer “Volume Sales” over “Unit Sales” (when available)

#### Simple explanation

**What is Volume Sales?**  
Volume Sales measures actual consumption volume in standardized units. Circana defines **1 volume unit = 204 fluid ounces** (a 12-pack). This lets us compare across pack sizes fairly:

- A 12-pack = 1 volume unit
- A 24-pack = 2 volume units

So selling 100 small packs can equal selling 50 large packs — same consumption volume.

#### Why this matters for price elasticity

If consumers “trade down” to smaller packs when prices rise, **Unit Sales can stay flat** even though **consumption volume falls**. Elasticity computed on Unit Sales can be biased toward “less elastic” simply because pack mix shifted.

Example (two weeks):

Week 1: Price = $18  
- Sales mix: 80% twenty-four-packs + 20% twelve-packs  
- Unit Sales: 1,000 units  
- Volume Sales: (800 × 2) + (200 × 1) = 1,800  

Week 2: Price = $20  
- Sales mix: 20% twenty-four-packs + 80% twelve-packs  
- Unit Sales: 1,000 units  
- Volume Sales: (200 × 2) + (800 × 1) = 1,200  

Using **UNIT SALES**:
- Price up ~11%, units flat → conclusion: perfectly inelastic (**wrong**)

Using **VOLUME SALES**:
- Price up ~11%, volume down ~33% → conclusion: highly elastic (**more correct**)

#### For technical audiences

We prefer Volume Sales over Unit Sales to normalize across **pack-size heterogeneity**. Circana’s volume standardization (1 unit = 204 oz) helps ensure elasticity estimates aren’t biased by shifts in the pack-size mix (e.g., 24-pack → 12-pack trading).

> Note: the current pipeline uses `Unit Sales` as the dependent variable. If your Circana extracts include Volume Sales fields and you want the model to use them, we can wire that in (minimal change in `data_prep.py` + docs).

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
