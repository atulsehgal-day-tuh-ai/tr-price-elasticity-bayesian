## How to run this repo (step-by-step, with validation)

This guide is intentionally **verbose**. It’s written for “I have a new VM / new laptop and I want a reliable checklist” use.

At a high level, when you run this system you are doing four things:

- **Prepare data**: read one or more retailer CSVs and transform them into a clean, model-ready weekly dataset
- **Fit a Bayesian elasticity model**: run MCMC (multiple chains) to estimate elasticity parameters with uncertainty
- **Save artifacts**: CSV outputs + text summary + (optional) full posterior trace
- **Generate diagnostics & a shareable report**: plots + a self-contained HTML report

The main entrypoint is:

- `run_analysis.py` (CLI “conductor” that calls data prep + model fit + outputs)

If you’re not sure where to start: run an example first, then run the production pipeline with a YAML config.

---

## 0) What “running the code” means in this repo

You’ll typically run one of these:

- **Example scripts** (fastest way to smoke-test your environment):
  - `python examples/example_01_simple.py`
  - `python examples/example_02_hierarchical.py`
  - `python examples/example_05_base_vs_promo.py`
- **The pipeline CLI** (real “production style” runs):
  - `python run_analysis.py --config my_config.yaml --dual-elasticity`
  - or `python run_analysis.py --bjs data/bjs.csv --sams data/sams.csv --output ./results`

The pipeline writes a predictable set of outputs (details in the validation section):

- `prepared_data.csv`
- `model_summary.txt`
- `results_summary.csv`
- `trace.nc` (optional but enabled by default)
- `analysis.log`
- `plots/` (optional)
- `elasticity_report.html` (optional)

---

## 1) Prerequisites (what you need before you start)

### 1.1 Python version

This repo is easiest to run with **Python 3.12.x**.

On Linux:

```bash
python3.12 --version
```

If you only have `python3`:

```bash
python3 --version
```

### 1.2 OS packages (Linux)

Most pip dependencies here are pre-built wheels, but it’s still a good idea to have build tools installed for scientific packages.

On Ubuntu:

```bash
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv build-essential g++
```

### 1.3 Data files

You need one or more retailer CSVs. Typical inputs are:

- `data/bjs.csv` (Circana-style)
- `data/sams.csv` (Circana-style)
- `data/costco.csv` (Costco CRX-style; optional)

If you don’t have them on the VM yet, see the “Upload data” section.

---

## 2) Get into the repo folder (important)

Most “file not found” errors happen because you’re in the wrong directory.

```bash
cd /home/azureuser/tr-price-elasticity-bayesian
pwd
ls
```

**Purpose of these commands:**

- `cd ...`: ensures relative paths like `./venv312/...` and `./data/...` resolve correctly
- `pwd`: prints your current directory so you can visually confirm it
- `ls`: confirms you’re in the repo (you should see `run_analysis.py`, `requirements.txt`, `scripts/`, etc.)

---

## 2.1 (Optional but recommended) Enable `git push` from the VM (GitHub SSH key)

If you plan to edit code/docs on the VM and push back to GitHub, you need the VM to authenticate to GitHub.

### Why you might need this

If your repo remote looks like an HTTPS URL (example):

- `https://github.com/<org-or-user>/<repo>.git`

…then `git push` usually requires credentials. On a headless VM, that often fails with:

- `could not read Username for 'https://github.com': No such device or address`

The most reliable fix is to use **SSH** with a key.

### Step A — Generate an SSH key on the VM (one-time)

Run on the VM:

```bash
mkdir -p ~/.ssh
chmod 700 ~/.ssh
ssh-keygen -t ed25519 -C "vm-mcmc-bayesian" -f ~/.ssh/id_ed25519 -N ""
```

This creates:

- `~/.ssh/id_ed25519` (private key — keep secret)
- `~/.ssh/id_ed25519.pub` (public key — safe to share)

### Step B — Add the VM’s *public key* to GitHub (one-time)

1. On the VM, copy the public key text:

```bash
cat ~/.ssh/id_ed25519.pub
```

2. In GitHub (web UI):

- Profile icon (top-right) → **Settings**
- **SSH and GPG keys**
- **New SSH key**

3. Fill the form as follows:

- **Title**: something descriptive like `vm-mcmc-bayesian (Azure VM)`
- **Key type**: **Authentication Key**
- **Key**: paste the *entire* `ssh-ed25519 ...` line you copied from the VM

4. Click **Add SSH key**

> Alternative (repo-scoped): Repo → **Settings** → **Deploy keys** → **Add deploy key** → paste the same key and **check “Allow write access”** (required for push).

### Step C — Switch your git remote to SSH and test

Run on the VM:

```bash
ssh-keyscan -t ed25519 github.com >> ~/.ssh/known_hosts
chmod 600 ~/.ssh/known_hosts
```

Switch remote (example):

```bash
git remote set-url origin git@github.com:<org-or-user>/<repo>.git
git remote -v
```

Test auth:

```bash
ssh -T git@github.com
```

Expected:

- A message like “You’ve successfully authenticated…”

Finally, push:

```bash
git push
```

---

## 3) Create a virtual environment + install dependencies

Why you want a venv:

- Keeps the repo’s Python packages isolated from system Python
- Avoids dependency conflicts between projects
- Makes runs reproducible (“this is the environment that produced these results”)

### 3.1 Linux / VM (recommended path for this repo)

This repo includes a script that:

- creates a venv at `./venv312`
- upgrades pip inside it
- installs `requirements.txt`

Run:

```bash
bash ./scripts/setup_venv_py312_linux.sh
```

**Purpose:**

- `bash ...`: runs the setup script to build a clean environment for the project

**Important behavior:**

- The script **deletes and recreates** `./venv312`. That’s great for a clean rebuild, but don’t store anything important inside that folder.

### 3.2 Windows (PowerShell)

If you’re on Windows (PowerShell), there’s also a script:

```powershell
.\scripts\setup_venv_py312_windows.ps1
```

---

## 4) Activate the venv (Linux)

Activation on Linux must be **sourced** (so it modifies your *current shell* environment variables like `PATH`):

```bash
source ./venv312/bin/activate
```

**Purpose:**

- After activation, `python` and `pip` refer to the versions inside the venv

### 4.1 Verify you activated the right Python

```bash
which python
python --version
pip --version
```

You should see paths that include `.../tr-price-elasticity-bayesian/venv312/...`.

### 4.2 Deactivate when you’re done

```bash
deactivate
```

---

## 5) Upload data files from your local machine to the VM

There are many ways to do this. The key point is:

- `scp` / `rsync` commands run on **your local machine**, and copy files **to** the VM.

### 5.1 Upload with scp (simple)

On your **local machine terminal**:

```bash
scp /path/to/local/bjs.csv azureuser@<VM_PUBLIC_IP_OR_HOSTNAME>:/home/azureuser/tr-price-elasticity-bayesian/data/
scp /path/to/local/sams.csv azureuser@<VM_PUBLIC_IP_OR_HOSTNAME>:/home/azureuser/tr-price-elasticity-bayesian/data/
```

Multiple files at once (Linux/macOS bash **only**, brace expansion):

```bash
scp /path/to/local/{bjs.csv,sams.csv,costco.csv} azureuser@<VM_PUBLIC_IP_OR_HOSTNAME>:/home/azureuser/tr-price-elasticity-bayesian/data/
```

Windows (PowerShell): **do not** use `{a,b,c}` brace expansion. Instead, list each file explicitly (you can pass multiple source paths in one `scp` command):

```powershell
scp -i C:/Users/atulsehgal/.ssh/vm-mcmc-bayesian_key.pem `
  C:/repos/tr-price-elasticity-bayesian/data/bjs.csv `
  C:/repos/tr-price-elasticity-bayesian/data/sams.csv `
  C:/repos/tr-price-elasticity-bayesian/data/costco.csv `
  azureuser@20.94.79.51:/home/azureuser/tr-price-elasticity-bayesian/data/
```

Notes (Windows PowerShell):

- The `-i <path-to-key.pem>` is required if your VM is configured for **SSH key auth** (common for Azure VMs).
- Backticks (`` ` ``) are PowerShell line-continuations; you can also put the whole command on one line.
- Alternative if all your files are in one folder:

```powershell
scp -i C:/Users/atulsehgal/.ssh/vm-mcmc-bayesian_key.pem C:/repos/tr-price-elasticity-bayesian/data/*.csv azureuser@20.94.79.51:/home/azureuser/tr-price-elasticity-bayesian/data/
```

If you use an SSH key (Linux/macOS):

```bash
scp -i /path/to/key.pem /path/to/local/bjs.csv azureuser@<VM_PUBLIC_IP_OR_HOSTNAME>:/home/azureuser/tr-price-elasticity-bayesian/data/
```

### 5.2 Upload with rsync (best for large files / resume)

On your **local machine terminal**:

```bash
rsync -avP /path/to/local/data/ azureuser@<VM_PUBLIC_IP_OR_HOSTNAME>:/home/azureuser/tr-price-elasticity-bayesian/data/
```

### 5.3 Verify the files arrived (run on the VM)

On the VM:

```bash
cd /home/azureuser/tr-price-elasticity-bayesian
ls -lh ./data
```

**Purpose:**

- Confirms the files exist where the code expects them (or where your config points)

---

## 5.4 Data transformation validation (recommended before model fitting)

Before you trust any elasticity results, you should build confidence that the **data transformation** is correct. The fastest way is to use the exploration notebook:

- `notebooks/01_data_transformation_exploration.ipynb`

Why this notebook is valuable:

- It runs `ElasticityDataPrep.transform(...)` and shows intermediate sanity checks
- It produces a saved, auditable artifact: `results/prepared_data_from_notebook.csv`
- It makes it easy to spot schema/parsing issues (especially for Costco CRX)

### How to use it (high level)

1. Activate your venv
2. Start Jupyter
3. Open `notebooks/01_data_transformation_exploration.ipynb`
4. Run cells top-to-bottom

### What to verify in the notebook (the “confidence checklist”)

- **Retailers present**: you should see BJ’s + Sam’s; and Costco if `data/costco.csv` exists
- **Date range** matches your source files
- **No obviously broken values**:
  - prices are positive and within a plausible range
  - volume sales are positive
  - log columns do not contain `inf`/`-inf`
- **Promo depth** looks right:
  - `Promo_Depth_SI` is near 0 most weeks and negative on discounted weeks (e.g., −0.10 ≈ 10% off)
- **Availability masks** look right:
  - Costco should typically have `has_competitor = 0` (no private label rows)
- **Export exists**: `results/prepared_data_from_notebook.csv` is written and looks sane

### Other ways to gain confidence in transformation (in addition to the notebook)

Beyond eyeballing plots, the most reliable methods are:

- **Audit artifact**: treat `prepared_data.csv` / `prepared_data_from_notebook.csv` as the “source of truth” and inspect counts, ranges, and missingness by retailer.
- **Schema checks**: assert required columns exist and no `inf`/`-inf` appears in log columns.
- **Retailer-by-retailer summaries**: min/max dates, row counts, price ranges, promo depth distributions, and mask flags (`has_promo` / `has_competitor`) per retailer.
- **Spot-check a few weeks** against raw source rows (especially Costco avg/base price math).

If the notebook fails or looks suspicious, fix data transformation first (contracts, factors, file paths) before fitting models.

---

## 6) First run (recommended): example scripts

Before you do a full pipeline run, run an example. Examples are the fastest way to confirm:

- your venv works
- dependencies are installed
- the code can run end-to-end

Make sure you have activated the venv first:

```bash
cd /home/azureuser/tr-price-elasticity-bayesian
source ./venv312/bin/activate
```

### 6.1 Example 01 — simple model (best smoke test)

```bash
python examples/example_01_simple.py
```

**What you are running:**

- A minimal end-to-end analysis using the **simple** (non-hierarchical) model.

**Purpose:**

- Establishes that your environment can load data, fit a model, and produce outputs.

**Verify (quick):**

- You should see a printed model summary (including R-hat / ESS / divergences).
- If the script produces an output folder (commonly `output_example_01/`), verify it exists and contains an HTML report.

### 6.2 Example 02 — hierarchical model (multi-retailer)

```bash
python examples/example_02_hierarchical.py
```

**What you are running:**

- A hierarchical Bayesian model that can estimate retailer-specific effects with partial pooling.

**Purpose:**

- Confirms the group-level machinery works (and is typically closer to “real use”).

**Verify (quick):**

- The output should list retailers found in the data (e.g., BJ’s, Sam’s Club, and optionally Costco if your script/config includes it).
- The script should print global + retailer-specific elasticities.

### 6.3 Example 03 — adding custom features (extending the model inputs)

```bash
python examples/example_03_add_features.py
```

**What you are running:**

- A guided example that shows feature engineering patterns (interactions, lags, moving averages, custom formulas) and how those new columns flow into modeling.

**Why this was not listed earlier:**

- It’s not needed to prove the system runs end-to-end. It’s for the “next phase” once you trust the baseline transformation + model and want to extend inputs.

**Verify (quick):**

- Look for a created output folder like `output_example_03/`.
- Confirm the new engineered columns exist in the transformed DataFrame (the script prints/logs them).

### 6.4 Example 04 — Costco (heterogeneous schema + missing-feature handling)

```bash
python examples/example_04_costco.py
```

**What you are running:**

- A three-retailer hierarchical run designed to demonstrate handling heterogeneous retailers and missing data using availability flags.\n+
**Why this was not listed earlier:**

- It is slightly more operationally demanding (requires `data/costco.csv` and, for best results, correct contracts/factors), so it’s best after you’ve validated transformation with the notebook.

**Verify (quick):**

- The script should print a retailer list including `Costco`.
- It should write an HTML report in `output_example_04/` (typically `costco_missing_promo_report.html`).

### 6.5 Example 05 — base vs promo elasticity (V2)

```bash
python examples/example_05_base_vs_promo.py
```

**What you are running:**

- The “dual elasticity” approach:
  - **Base price elasticity** (strategic, long-run)
  - **Promotional elasticity** (tactical, discount responsiveness)

**Purpose:**

- Confirms that base vs promo separation is working and produces the comparison outputs.

**Verify (quick):**

- The results should include both **Base Price Elasticity** and **Promotional Elasticity**.
- If a report is generated, confirm it includes a “base vs promo” comparison section/plot.

---

## 7) Production run (recommended): YAML config + `run_analysis.py`

### 7.1 Create a config from the template

From repo root:

```bash
cp config_template.yaml my_config.yaml
```

**Purpose:**

- You keep `config_template.yaml` as an unchanged reference
- You edit `my_config.yaml` for your actual file paths and modeling choices

### 7.2 Config vs CLI precedence (important)

`run_analysis.py` works in **two modes**:

- **Config mode**: you provide `--config my_config.yaml`
  - In this mode, the YAML is the source of truth for paths, model type, sampling params, and output toggles.
- **CLI mode**: you provide file paths like `--bjs ... --sams ...`
  - In this mode, `run_analysis.py` builds a config internally from your flags.

Rule of thumb:

- If you pass `--config`, focus on editing the YAML.
- If you are experimenting quickly, use CLI flags.

### 7.2 Edit `my_config.yaml` (what matters first)

Most important fields to get right for a first real run:

- `data.bjs_path`, `data.sams_path`, `data.costco_path` (or set Costco to `null`)
- `data.retailer_filter`
  - `"Overall"` combines retailers into one dataset
  - `"All"` keeps retailers separate (required for hierarchical modeling)
- `data.volume_sales_factor_by_retailer`
  - required for any retailer missing a `Volume Sales` column (e.g., Costco)
- `model.type`
  - `"simple"` for one pooled model
  - `"hierarchical"` for retailer-specific estimates with pooling
- `output.output_dir`

### 7.3 Run the pipeline

With dual elasticity enabled (recommended; it is also the default behavior):

```bash
python run_analysis.py --config my_config.yaml --dual-elasticity
```

Notes:

- Dual elasticity is **already the default** behavior in the code. The `--dual-elasticity` flag is mostly there for explicitness.
- If you ever need legacy behavior, you can disable it with:

```bash
python run_analysis.py --config my_config.yaml --no-dual-elasticity
```

Or if you prefer to pass file paths directly (no YAML):

```bash
python run_analysis.py \
  --bjs data/bjs.csv \
  --sams data/sams.csv \
  --hierarchical \
  --output ./results
```

**What you are running:**

`run_analysis.py` orchestrates:

- Step 1: `ElasticityDataPrep.transform(...)` (load → clean → feature engineering → validation)
- Step 2: model fit via PyMC (MCMC sampling)
- Step 3: save results + trace
- Step 4: generate plots (optional)
- Step 5: generate an HTML report (optional)

**Purpose:**

- This is the main “production pipeline” run that creates shareable outputs for stakeholders.

---

## 8) Where to look: outputs and what they mean

The output directory is controlled by:

- CLI: `--output ./results`
- YAML: `output.output_dir: "./results"`

The pipeline writes:

- `analysis.log`
  - full run log (good for debugging)
- `prepared_data.csv`
  - the **exact** dataset used by the model (this is your primary audit artifact)
- `model_summary.txt`
  - text summary including convergence diagnostics and posterior summaries
- `results_summary.csv`
  - a small table of key elasticities + credible intervals
- `trace.nc` (if enabled)
  - full posterior samples (ArviZ netCDF)
- `plots/` (if enabled)
  - diagnostic plots in PNG form (trace, posteriors, scenarios, etc.)
- `elasticity_report.html` (if enabled)
  - a self-contained HTML report with embedded plots and tables

### 8.1 How to view the HTML report on a VM

If you’re running on a remote VM, you have a few options:

**Option A: Open it in your editor (Cursor/VS Code Remote)**

- In the file explorer, find `elasticity_report.html`
- Use your editor’s “Open Preview” / “Open in Browser” feature

**Option B: Copy it to your laptop with scp**

Run on your **local machine**:

```bash
scp azureuser@<VM_PUBLIC_IP_OR_HOSTNAME>:/home/azureuser/tr-price-elasticity-bayesian/results/elasticity_report.html .
```

Then open it locally in a browser.

**Option C: Serve it from the VM (requires network access)**

On the VM, in the output directory:

```bash
cd /home/azureuser/tr-price-elasticity-bayesian/results
python -m http.server 8000
```

Then open in your browser:

- `http://<VM_PUBLIC_IP_OR_HOSTNAME>:8000/elasticity_report.html`

If it doesn’t load, your VM firewall / cloud security group likely blocks port 8000.

---

## 9) Validate the results (do this every run)

Validation here means:

- The run finished successfully
- The model actually converged (or you understand what warning you got)
- The numbers are directionally reasonable and consistent with the data
- The artifacts you need for analysis / sharing exist

### 9.1 Validate the run completed and created the expected files

In your output directory (example: `./results`):

```bash
ls -lh ./results
```

You should see most or all of:

- `analysis.log`
- `prepared_data.csv`
- `model_summary.txt`
- `results_summary.csv`
- `trace.nc`
- `elasticity_report.html`
- `plots/` (folder)

If something is missing:

- Check the flags you used (`--no-html`, `--no-plots`)
- Check `analysis.log` for the failure point

### 9.2 Validate the prepared dataset looks sane (`prepared_data.csv`)

This is the single most important “audit” file.

Basic checks:

```bash
python -c "import pandas as pd; df=pd.read_csv('./results/prepared_data.csv'); print(df.shape); print(df.columns.tolist()[:25]); print(df[['Date','Retailer']].head())"
```

What you want to see:

- **Row count is non-trivial** (not 0, not tiny unless you intentionally filtered hard)
- **Date** spans the expected period
- If you ran hierarchical: you should have a `Retailer` column with expected values
- You should see model features like:
  - `Log_Volume_Sales_SI`
  - `Log_Base_Price_SI` (V2 base) or `Log_Price_SI` (legacy)
  - `Promo_Depth_SI` (V2) and/or a promo intensity feature
  - `has_promo`, `has_competitor` (masks for missing retailer features)

If this file looks wrong, **stop** and fix data prep before trusting model results.

### 9.3 Validate convergence (R-hat, ESS, divergences)

Convergence criteria used by the code:

- **Max R-hat < 1.01**
- **Min ESS > 400**
- **Divergences = 0**

Where to check:

- In console output at the end of the run
- In `model_summary.txt`
- In the HTML report header (it prints convergence status)

What the diagnostics mean (short version):

- **R-hat** near 1.0 means chains agree (good mixing)
- **ESS** is “how many independent-ish samples you effectively have” (bigger is better)
- **Divergences** are a sign the sampler struggled with the posterior geometry (you want 0)

If you fail convergence:

- Increase sampling: `--samples`, `--tune`, or YAML `model.n_samples`, `model.n_tune`
- Increase `target_accept` slightly (e.g. 0.97)
- Investigate data issues (outliers, missingness, extreme promo depths, etc.)

### 9.3.1 Quick “smoke test” mode (fast run to validate plumbing)

When you are still wiring up data paths and just want to confirm the pipeline runs,
use a smaller sampling configuration and skip report generation:

```bash
python run_analysis.py \
  --bjs data/bjs.csv \
  --sams data/sams.csv \
  --hierarchical \
  --samples 300 \
  --tune 300 \
  --chains 2 \
  --no-plots \
  --no-html \
  --output ./results_smoke
```

**Purpose:**

- This is *not* for final numbers. It’s to catch:
  - “file not found”
  - schema/column issues
  - obvious data prep failures
  - missing dependencies

Once it runs cleanly, switch back to the default sampling settings and enable HTML/plots.

### 9.4 Validate elasticity direction and magnitude (sanity expectations)

This repo uses log-log style relationships. Typical sanity expectations:

- **Base price elasticity** should usually be **negative**
  - price up → volume down
- **Promotional elasticity** (if estimated) should usually be **negative** and often **larger magnitude than base**
  - discounts tend to create stronger short-run response than permanent base price moves
- **Cross-price elasticity** (if competitor exists) is often **small positive**
  - competitor price up → your volume up

How to check quickly:

```bash
cat ./results/results_summary.csv
```

What to look for:

- Credible intervals should be reasonably tight for stable runs
- CIs that straddle 0 mean “we’re not sure about the sign”

If elasticities have surprising signs:

- Double-check feature definitions (especially promo depth sign)
- Confirm the correct price columns were used (avg price vs base price)
- Confirm you filtered the right products / brands

### 9.5 Validate the diagnostic plots (trace + posteriors)

Open the report:

- `./results/elasticity_report.html`

Or inspect images:

- `./results/trace_plot.png` (if you generated the HTML report)
- `./results/plots/trace.png` (if you generated plots)

What you want to see in the trace plot:

- Chains look like “hairy caterpillars” (good mixing)
- No strong trends over time
- Chains overlap heavily

What you want to see in posterior plots:

- Parameters have reasonable distributions (not crazy wide, not multi-modal without explanation)

### 9.6 Validate revenue scenario logic (base vs promo)

In V2, the report generates:

- `revenue_scenarios_base.png`
- `revenue_scenarios_promo.png` (only if promo elasticity was estimated)

Sanity expectations:

- For **base price increases**:
  - If demand is elastic (\(|\epsilon|>1\)), revenue impact tends to be negative for price increases
  - If demand is inelastic (\(|\epsilon|<1\)), revenue impact tends to be positive for small increases
- For **promotions**:
  - Deeper discounts should usually increase volume a lot, but revenue can go either way depending on elasticity magnitude

Use the HTML report tables for quick “expected vs probability positive” checks.

---

## 10) Reproducibility (so you can re-run and get comparable results)

MCMC is stochastic, but you can still control major sources of variability.

Things that help reproducibility:

- Keep your `my_config.yaml` checked in (or at least saved)
- Keep the exact `prepared_data.csv` from the run
- Use a fixed seed:
  - CLI: `--seed 42`
  - YAML: `model.random_seed: 42`

If you change:

- sampling parameters (`samples`, `tune`, `chains`)
- priors
- data filtering logic
- data contracts

…you should treat that as a new “version” of the run and keep outputs separate (e.g., a new output directory).

## 11) Running on a VM reliably (tmux for long runs)

MCMC can take minutes to hours. If you’re connected over SSH, use `tmux` so your job keeps running even if you disconnect.

Start a tmux session:

```bash
tmux new -s mcmc
```

Inside tmux, activate venv + run:

```bash
cd /home/azureuser/tr-price-elasticity-bayesian
source ./venv312/bin/activate
python run_analysis.py --config my_config.yaml --dual-elasticity
```

Detach (leave it running): `Ctrl+B`, then `D`

Reattach later:

```bash
tmux attach -t mcmc
```

---

## 12) Common errors and fixes

### 11.1 `./venv312/bin/activate: No such file or directory`

Causes:

- You’re not in the repo root
- You never created `venv312`

Fix:

```bash
cd /home/azureuser/tr-price-elasticity-bayesian
bash ./scripts/setup_venv_py312_linux.sh
source ./venv312/bin/activate
```

### 11.2 Activation “works locally but not on VM”

Usually you are using different shells / OS:

- Linux/macOS: `source venv/bin/activate`
- Windows PowerShell: `.\venv\Scripts\Activate.ps1`
- Windows cmd.exe: `venv\Scripts\activate.bat`

### 11.3 Data prep fails complaining about Volume Sales

This repo’s rule is: **the dependent variable is Volume Sales**.

If a retailer file doesn’t have a `Volume Sales` column, you must provide:

- `data.volume_sales_factor_by_retailer` in your YAML, or
- CLI args: `--volume-sales-factor Retailer=FACTOR`

Example:

```bash
python run_analysis.py \
  --bjs data/bjs.csv \
  --sams data/sams.csv \
  --costco data/costco.csv \
  --hierarchical \
  --volume-sales-factor Costco=2.0 \
  --output ./results
```

### 11.4 Convergence warnings

If you see warnings like:

- R-hat too high
- ESS too low
- divergences > 0

Typical fixes:

- increase tuning (`--tune 2000`)
- increase samples (`--samples 4000`)
- raise target accept (YAML: `model.target_accept: 0.97`)

---

## 13) Recommended “first real run” checklist

1) Confirm you’re in the repo root:

```bash
cd /home/azureuser/tr-price-elasticity-bayesian
```

2) Create/install venv:

```bash
bash ./scripts/setup_venv_py312_linux.sh
```

3) Activate:

```bash
source ./venv312/bin/activate
```

4) Confirm data exists:

```bash
ls -lh ./data
```

5) Create config and edit paths:

```bash
cp config_template.yaml my_config.yaml
```

6) Run:

```bash
python run_analysis.py --config my_config.yaml --dual-elasticity
```

7) Validate outputs:

```bash
ls -lh ./results
cat ./results/results_summary.csv
```

8) Open `./results/elasticity_report.html` and check:

- convergence box (R-hat, ESS, divergences)
- base vs promo elasticities
- revenue scenario plots and tables

