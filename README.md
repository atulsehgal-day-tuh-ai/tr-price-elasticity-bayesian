# Price Elasticity Bayesian Analysis System

A complete, production-ready system for Bayesian price elasticity analysis with hierarchical modeling, uncertainty quantification, and comprehensive visualizations.

## 🎯 Features

- **Data Transformation**: Automated pipeline from raw Circana data to model-ready format
- **Bayesian Modeling (V2)**: Simple and hierarchical models with **dual elasticities** (base vs promo)
- **Base vs Promo Separation (V2)**: Separates strategic (base price) impact from tactical (promotional discount) impact
- **Hierarchical Support**: Multi-retailer analysis with automatic shrinkage
- **Flexible Priors**: Default (weakly informative), informative, vague, or custom
- **Missing Data Handling**: Automatically handles retailers with missing features (e.g., Costco without Private Label / competitor data)
- **Feature Engineering**: Easy-to-use methods for creating custom features
- **Comprehensive Visualizations**: Trace plots, posterior distributions, seasonal patterns, revenue scenarios
- **HTML Reports**: Complete interactive reports with all analyses
- **Uncertainty Quantification**: Full posterior distributions and probability statements

## 📋 Requirements

- Python **3.12.x** (recommended)
- PyMC 5.10+
- See `requirements.txt` for full list

## 🚀 Quick Start

### Installation

```bash
# Install dependencies
pip install -r requirements.txt
```

### Python 3.12 (recommended) + virtual environment

This project is easiest to run in a dedicated venv using **Python 3.12.x**.

- **Windows (PowerShell)**:

```powershell
.\scripts\setup_venv_py312_windows.ps1
.\venv312\Scripts\Activate.ps1
python --version
```

- **Linux (e.g., Azure VM)**:

```bash
bash ./scripts/setup_venv_py312_linux.sh
source ./venv312/bin/activate
python --version
```

### Markdown → HTML (for sharing business docs)

To export a guide from `help_documents/` into a “paper-style” HTML file in `html/`:

- **Windows (PowerShell)**:

```powershell
.\scripts\convert_help_md_to_html.ps1 -InputMd "Sparkling_Ice_Analytics_Plan_Business_Guide.md"
```

- **Linux/macOS (bash)**:

```bash
bash ./scripts/convert_help_md_to_html.sh Sparkling_Ice_Analytics_Plan_Business_Guide.md
```

### Cloud setup (Cursor + GitHub Codespaces) — 16 cores / 64 GB RAM

This repo supports running in GitHub Codespaces (and connecting from Cursor) via a Dev Container.

> If you are running via **local venv** (or via an **SSH VM**), you do **not** need Docker or the devcontainer. It’s only for Codespaces / Dev Containers.

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
- Total sales columns: `Dollar Sales`, `Unit Sales`, `Volume Sales` (preferred dependent variable)
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

> Note: the pipeline **uses `Volume Sales` as the dependent variable** (when present). If a retailer file is missing `Volume Sales`, the pipeline can compute it as `Unit Sales × factor` (configure `volume_sales_factor_by_retailer` in your config). If neither `Volume Sales` nor a factor is available, the pipeline fails fast with a clear error.

### Command Line

```bash
# Run complete analysis
python run_analysis.py --bjs bjs.csv --sams sams.csv --output ./results

# With custom configuration
python run_analysis.py --config my_config.yaml
```

## 📖 Documentation

### Architecture (how it all connects)

See **`help_documents/architecture.md`** for a detailed architecture diagram, module responsibilities, call graphs, and the end-to-end data/model/report flow.

### Business / stakeholder guides (recommended for non-technical audiences)

The `help_documents/` folder contains the primary narrative guides for this work:

- **`help_documents/Sparkling_Ice_Analytics_Plan_Business_Guide.md`**: The business-friendly end-to-end story (Bayesian vs classical, MCMC, why compute matters, dual elasticities, seasonality/holidays, hierarchical pooling, and which questions we answer).
- **`help_documents/Sparkling_Ice_Analytics_Plan_Techno_Functional_Guide.md`**: A combined business + technical guide (model/data contracts, raw columns used, engineered features, conceptual equations, implementation pointers).
- **`help_documents/Azure_VM_Cursor_MCMC_Setup_Guide.md`**: How to run the project on a VM via Cursor/SSH (kept separate from the modeling narrative).

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
    PrepConfig(
        retailers={
            'BJs': {'has_promo': True, 'has_competitor': True},
            'Sams': {'has_promo': True, 'has_competitor': True},
            # Costco CRX typically has promo data, but does not include Private Label rows for cross-price.
            'Costco': {'has_promo': True, 'has_competitor': False}
        },
        # If Costco (or another retailer) is missing `Volume Sales`, provide a constant factor
        # so data prep can compute: Volume Sales = Unit Sales × factor.
        volume_sales_factor_by_retailer={'Costco': 2.0}
    )
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

#### Model equation (V2 dual-elasticity; **implemented**)

In V2 dual-elasticity mode (default), the model is fit on weekly data in log space:

\[
Log\_Volume\_Sales\_{SI,t} = \alpha
+ \beta_{base} \cdot Log\_Base\_Price\_{SI,t}
+ \beta_{promo} \cdot (Promo\_Depth\_{SI,t} \cdot has\_promo_t)
+ \beta_{cross} \cdot (Log\_Price\_{PL,t} \cdot has\_competitor_t)
+ \beta_{spring} \cdot Spring_t
+ \beta_{summer} \cdot Summer_t
+ \beta_{fall} \cdot Fall_t
+ \beta_{time} \cdot Week\_Number_t
+ \epsilon_t
\]

with \(\epsilon_t \sim \mathcal{N}(0, \sigma)\).

**Sources / calculations (raw retailer exports → engineered features; contract-driven):**
- **`Log_Volume_Sales_SI` (dependent variable)**  
  - **Source**: Sparkling Ice `Volume Sales` (raw column: `Volume Sales`) after filtering `Product` to Sparkling Ice aggregate and pivoting to `Volume_Sales_SI`
  - **Fallback (strict)**: if `Volume Sales` is missing for a retailer, compute `Volume Sales = Unit Sales × factor` using `PrepConfig.volume_sales_factor_by_retailer`
  - **Transform**: `Log_Volume_Sales_SI = ln(Volume_Sales_SI)` (requires `Volume_Sales_SI > 0`)

- **`Log_Base_Price_SI` (strategic/base price term)**  
  - **Source (Circana; BJ’s/Sam’s)**: `Base Dollar Sales`, `Base Unit Sales` → `Base_Price_SI = Base_Dollar_Sales_SI / Base_Unit_Sales_SI`
  - **Source (Costco CRX)**: `Non Promoted Dollars`, `Non Promoted Units` → `Base_Price_SI = Non Promoted Dollars / Non Promoted Units` (with fallback to `Average Price per Unit` when non-promoted units are below the contract threshold)
  - **Guardrails**: if base sales columns are missing/undefined for weeks, the pipeline imputes a proxy `Base_Price_SI` from observed average prices (see `PrepConfig.base_price_proxy_window` and `base_price_imputed_warn_threshold`)
  - **Transform**: `Log_Base_Price_SI = ln(Base_Price_SI)` (requires `Base_Price_SI > 0`)

- **`Promo_Depth_SI` (tactical/promo term)**  
  - **Source**:
    - `Avg_Price_SI` is contract-driven:
      - Circana: `Avg_Price_SI = Dollar_Sales_SI / Unit_Sales_SI`
      - Costco CRX: `Avg_Price_SI = Avg Net Price`
    - `Promo_Depth_SI = (Avg_Price_SI / Base_Price_SI) - 1` (negative when discounted)
  - **Stability**: NaN/inf handled and values are clipped to a reasonable range for robustness

- **`Log_Price_PL` (private label / cross-price control)**  
  - **Source**: Private Label aggregate → `Price_PL = Dollar_Sales_PL / Unit_Sales_PL` then `Log_Price_PL = ln(Price_PL)`
  - **Missingness**: if competitor/private label price is not available for a retailer, the model uses `has_competitor_t = 0` so the cross-price term contributes 0

- **`Spring`, `Summer`, `Fall` (seasonality controls)**  
  - **Source**: derived from `Date` month (winter is the implicit baseline)

- **`Week_Number` (time trend control)**  
  - **Source**: weeks since first observation: `Week_Number = int((Date - min(Date)).days / 7)`

- **`has_promo`, `has_competitor` (availability masks)**  
  - **Source**: retailer configuration (`PrepConfig.retailers`) and/or inferred availability
  - **Purpose**: ensures missing promo/competitor features don’t bias estimation by zeroing out those terms

In hierarchical mode, the intercept and/or elasticities can vary by retailer with partial pooling.

**Notes / fallbacks:** if `Log_Base_Price_SI` / `Promo_Depth_SI` are unavailable (non-V2 mode), the code falls back to a legacy feature set (e.g., `Log_Price_SI` and optional `Promo_Intensity_SI`).

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
├── contract/
│   └── PROJECT_CONTRACT.md
├── notebooks/
│   └── 01_data_transformation_exploration.ipynb
├── help_documents/
│   ├── architecture.md
│   ├── Sparkling_Ice_Analytics_Plan_Business_Guide.md
│   ├── Sparkling_Ice_Analytics_Plan_Techno_Functional_Guide.md
│   └── Azure_VM_Cursor_MCMC_Setup_Guide.md
├── scripts/
│   ├── setup_venv_py312_windows.ps1
│   ├── setup_venv_py312_linux.sh
│   ├── convert_help_md_to_html.ps1
│   ├── convert_help_md_to_html.sh
│   └── md_to_html.py
└── examples/
    ├── example_01_simple.py
    ├── example_02_hierarchical.py
    ├── example_03_add_features.py
    ├── example_04_costco.py
    └── example_05_base_vs_promo.py
```

> The `html/` folder is created by the Markdown → HTML conversion scripts and is **gitignored** by default.

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
