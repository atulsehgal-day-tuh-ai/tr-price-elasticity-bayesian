# Run Book — Bayesian Price Elasticity Pipeline

> **Purpose:** Run the analysis pipeline end-to-end on your Azure VM.  
> **Assumes:** Your VM is set up and you know how to connect. If not → [Daily Driver](05b_azure_vm_daily_driver.md).

---

## The Workflow (Every Single Time)

This is your non-negotiable checklist. Do these steps in order, every run.

```
1. Start the VM          → Azure Portal or CLI (see below)
2. Connect Cursor        → Ctrl+Shift+P → Remote-SSH → azure-mcmc
3. Pull latest code      → git pull --ff-only
4. Activate venv         → source ./venv312/bin/activate
5. Run your code         → (inside tmux for long jobs)
6. Push your changes     → git add -A && git commit -m "msg" && git push
7. Deallocate the VM     → Azure Portal or CLI (see below)
```

> **Rule: always pull before you run, always push before you stop.**

### Step 1 — Start the VM

**Azure Portal:**
1. Go to [portal.azure.com](https://portal.azure.com)
2. Search **"Virtual machines"** → click **vm-mcmc-bayesian**
3. Click **▶ Start** → wait until Status = **Running**
4. Copy the **Public IP address** from the Overview page (update SSH config if it changed)

**Or CLI:**
```bash
az vm start --resource-group rg-bayesian-elasticity --name vm-mcmc-bayesian
```

### Step 7 — Deallocate the VM

**Azure Portal:**
1. Go to [portal.azure.com](https://portal.azure.com) → **Virtual machines** → **vm-mcmc-bayesian**
2. Click **⏹ Stop** → confirm
3. **Verify** status shows **"Stopped (deallocated)"** — not just "Stopped"

**Or CLI:**
```bash
az vm deallocate --resource-group rg-bayesian-elasticity --name vm-mcmc-bayesian
```

> ⚠️ "Stopped" ≠ "Deallocated." Only deallocated stops billing.

---

## Before You Run (First Time or After Changes)

### Confirm you're in the right place

```bash
cd /home/azureuser/tr-price-elasticity-bayesian
pwd       # should show the repo path
ls        # should show run_analysis.py, requirements.txt, scripts/, etc.
```

### Confirm venv works

```bash
source ./venv312/bin/activate
which python      # should point to .../venv312/bin/python
python --version  # should be 3.12.x
```

If the venv doesn't exist or is broken:
```bash
bash ./scripts/setup_venv_py312_linux.sh
source ./venv312/bin/activate
```

### Confirm data files exist

```bash
ls -lh ./data
```

You need at minimum `bjs.csv` and `sams.csv`. Optionally `costco.csv`.

If data is missing, upload from your local machine (PowerShell):
```powershell
scp -i C:/Users/<username>/.ssh/vm-mcmc-bayesian_key.pem `
  C:/path/to/bjs.csv `
  C:/path/to/sams.csv `
  azureuser@<PUBLIC_IP>:/home/azureuser/tr-price-elasticity-bayesian/data/
```

---

## Running the Pipeline

### Option A: Production run (YAML config)

```bash
# Create config from template (first time only)
cp config_template.yaml my_config.yaml

# Edit my_config.yaml — key fields:
#   data.bjs_path, data.sams_path, data.costco_path
#   data.retailer_filter ("All" for hierarchical, "Overall" for pooled)
#   data.volume_sales_factor_by_retailer (for Costco if no Volume Sales column)
#   model.type ("simple" or "hierarchical")
#   output.output_dir

# Run (always inside tmux for production runs)
tmux new -s mcmc
source ./venv312/bin/activate
python run_analysis.py --config my_config.yaml --dual-elasticity
```

> ⚠️ **Never overwrite previous results.** Always use a unique output directory per run.  
> The `--output` CLI flag may not override the YAML `output.output_dir` setting.  
> **Safest approach:** change `output.output_dir` directly in the config before each run.
>
> ```bash
> nano config_template.yaml
> # Ctrl+W → search "output_dir"
> # Change to: output_dir: "./results_v2"  (or v3, v4, etc.)
> # Ctrl+O → Enter → Ctrl+X
> ```
>
> **Naming convention:** use descriptive names that capture what changed:
> - `results_v1_baseline` — first run, default settings
> - `results_v2_target099` — raised target_accept to 0.99
> - `results_v3_tune2000` — increased tuning to 2000
>
> This gives you a full history of runs to compare and lets you trace back any final result to the exact config that produced it.

### Option B: Quick CLI run (no YAML)

```bash
python run_analysis.py \
  --bjs data/bjs.csv \
  --sams data/sams.csv \
  --hierarchical \
  --output ./results
```

### Option C: Smoke test (fast, validates plumbing)

```bash
python run_analysis.py \
  --bjs data/bjs.csv \
  --sams data/sams.csv \
  --hierarchical \
  --samples 300 --tune 300 --chains 2 \
  --no-plots --no-html \
  --output ./results_smoke
```

Use this to catch file-not-found, schema issues, and missing dependencies before committing to a full run.

### Option D: Example scripts (environment smoke test)

```bash
python examples/example_01_simple.py         # Simplest end-to-end test
python examples/example_06_smoke_beta_time_costco.py  # Costco + time trend + HTML
```

> Examples 01–05 may need minor touch-ups after recent pipeline changes. Example 06 is the most current.

---

## Expected Outputs

After a successful run, your output directory should contain:

| File | What It Is |
|------|-----------|
| `analysis.log` | Full run log — check here first if something fails |
| `prepared_data.csv` | Exact dataset fed to the model — your primary audit artifact |
| `model_summary.txt` | Convergence diagnostics + posterior summaries |
| `results_summary.csv` | Key elasticities + credible intervals |
| `trace.nc` | Full posterior samples (ArviZ netCDF) |
| `plots/` | Diagnostic PNGs (trace, posteriors, scenarios) |
| `elasticity_report.html` | Self-contained HTML report for stakeholders |

```bash
ls -lh ./results
```

---

## Validate Your Results

Do this **every run** — don't skip it.

### 1. Check convergence

```bash
grep -i "r_hat\|ess\|divergen" ./results/model_summary.txt
```

Or read the full summary:
```bash
cat ./results/model_summary.txt
```

| Metric | Good | Bad |
|--------|------|-----|
| R-hat | < 1.01 | > 1.01 (chains disagree) |
| ESS | > 400 | < 400 (not enough independent samples) |
| Divergences | 0 | > 0 (sampler struggled) |

### 2. Check elasticity direction

```bash
cat ./results/results_summary.csv
```

| Parameter | Expected Sign | Meaning |
|-----------|--------------|---------|
| Base price elasticity | Negative | Price up → volume down |
| Promotional elasticity | Negative (larger magnitude) | Discounts drive stronger response |
| Cross-price elasticity | Small positive | Competitor price up → your volume up |

### 3. Spot-check prepared_data.csv

```bash
python -c "
import pandas as pd
df = pd.read_csv('./results/prepared_data.csv')
print('Shape:', df.shape)
print('Retailers:', df['Retailer'].unique() if 'Retailer' in df.columns else 'N/A')
print('Date range:', df['Date'].min(), '→', df['Date'].max())
"
```

Verify: row count is sensible, date range matches your source data, retailers are correct.

---

## Iterating: What to Change When Results Aren't Clean

If your first run has convergence issues, **don't panic** — this is normal with Bayesian models. Here's how to iterate.

### The Iteration Loop

```
1. Check model_summary.txt → identify the problem
2. Edit config_template.yaml → change the relevant parameter
3. Re-run to a NEW output directory → compare against previous run
4. Repeat until convergence is clean and estimates are stable
```

> **Golden rule:** Always output to a new directory (e.g., `results_v2`, `results_v3`) so you can compare runs side by side.

### How to Edit the Config

```bash
nano config_template.yaml
```

- **Search for a parameter:** `Ctrl+W` → type the parameter name → **Enter**
- **Edit the value** on that line
- **Save:** `Ctrl+O` → **Enter**
- **Exit:** `Ctrl+X`
- **Verify your change:**
  ```bash
  grep <parameter_name> config_template.yaml
  ```

### How to Re-Run After a Config Change

```bash
tmux new -s mcmc2
source ./venv312/bin/activate
python run_analysis.py --config config_template.yaml --dual-elasticity --output ./results_v2
```

Detach: **`Ctrl+B` then `D`** — check back later: `tmux attach -t mcmc2`

### Understanding the Sampling Parameters

Before tuning, it helps to know what each parameter actually controls.

**`n_tune`** (warmup/burn-in steps) — The sampler's "learning phase." During tuning, the algorithm explores the posterior landscape and adjusts its internal step size. These samples are **thrown away** — they don't appear in your results. Think of it like warming up before a race. If the posterior has tricky geometry (sharp curves, narrow valleys), the sampler needs more warmup to learn how to navigate it.

**`n_samples`** (posterior draws per chain) — The "real" samples that become your results. After tuning, each chain draws this many samples from the posterior. More samples = tighter credible intervals and more stable estimates. But if the sampler hasn't learned the landscape well (not enough tuning), more samples just gives you more bad draws.

**`n_chains`** (parallel chains) — Independent runs of the sampler, each starting from a random point. Multiple chains let you check if they all converge to the same place (that's what R-hat measures). Standard practice is 4 chains. Rarely needs changing.

**`target_accept`** (acceptance rate) — Controls how "careful" the sampler is. Higher values (0.99) mean the sampler takes smaller, more cautious steps — it's less likely to stumble into bad regions (fewer divergences) but it moves slower (longer runtime). Lower values (0.90) mean bigger, bolder steps — faster but more prone to divergences. Default 0.95 is a good starting point; 0.99 is the go-to fix for divergences.

**`random_seed`** — Makes runs reproducible. Same seed + same config + same data = same results. Keep at 42 (or any fixed number) so you can re-run and compare fairly.

**How they relate:**

```
target_accept  →  Controls step quality (fix divergences first)
n_tune         →  Controls how well the sampler learns (fix next)
n_samples      →  Controls estimate precision (fix last)
n_chains       →  Controls convergence checking (rarely change)
```

> **Key insight:** If you have divergences, throwing more `n_samples` at the problem doesn't help — the sampler is taking bad steps. Fix `target_accept` and `n_tune` first, then increase `n_samples` if CIs are too wide.

### Reading the Live Progress Table

While the sampler runs, PyMC shows a live progress table — one row per chain:

```
Progress      Draws  Divergences  Step size  Grad evals  Sampling Speed  Elapsed  Remaining
██████░░░░░░  3504   1            0.003      1023        8.72 draws/s    0:06:41  0:06:54
██████░░░░░░  3499   0            0.003      1023        8.71 draws/s    0:06:41  0:07:01
██████░░░░░░  3525   0            0.002      1023        8.77 draws/s    0:06:41  0:07:00
██████░░░░░░  3503   1            0.003      1023        8.72 draws/s    0:06:41  0:07:03
```

Here's what each column means and how it connects to your config:

| Column | What It Means | Linked To |
|--------|--------------|-----------|
| **Progress** | Red bar = tuning (warmup), Blue bar = sampling (real draws). Red portion is your `n_tune`; blue is your `n_samples`. | `n_tune` + `n_samples` |
| **Draws** | How many posterior samples this chain has drawn so far (out of your `n_samples` target) | `n_samples` |
| **Divergences** | Bad steps taken so far in this chain. You want 0. Watch this column — if it's climbing fast, the run will have convergence issues. | `target_accept` (higher = fewer divergences) |
| **Step size** | How big a "step" the sampler takes each iteration. Smaller steps (0.002–0.003) = more cautious. This is what `target_accept` controls — higher target_accept forces smaller steps. | `target_accept` |
| **Grad evals** | Gradient evaluations per step. The sampler uses gradients (like reading the slope of a hill) to decide where to go. Higher numbers mean the sampler is exploring more deeply per step. | Internal (NUTS tree depth) |
| **Sampling Speed** | Draws per second across this chain. Tells you your CPU cores are working. | VM size (16 cores) |
| **Elapsed / Remaining** | Time spent and estimated time left. Total = tuning time + sampling time. | `n_tune` + `n_samples` + `target_accept` |

**What to watch for during a run:**

- **Divergences climbing steadily** → the run will likely need re-tuning. You can let it finish or kill it early (`Ctrl+C`) and adjust config.
- **Divergences at 0 across all chains** → looking good. Let it finish.
- **One chain much slower than others** → that chain may be stuck in a difficult region. Usually resolves, but if it hangs, more tuning helps.
- **Step size varies a lot between chains** (e.g., 0.001 vs 0.01) → chains are seeing different posterior geometry. Could indicate multimodality.

### Decision Guide: What to Change and Why

| What You See | Root Cause | What to Change | Where in Config |
|---|---|---|---|
| **Divergences > 0**, R-hat and ESS okay | Sampler taking bad steps | Raise `target_accept` (smaller, safer steps) | `model.target_accept: 0.99` |
| **Divergences > 0** even at 0.99 | Sampler hasn't learned the landscape | Increase `n_tune` (more warmup) | `model.n_tune: 3000` |
| **Divergences persist** after tune + target fixes | Posterior geometry is genuinely hard | Investigate which parameters diverge — may need model changes | Check trace plots for problematic params |
| **R-hat > 1.01** | Chains haven't agreed yet | Increase both `n_samples` and `n_tune` | `model.n_samples: 4000`, `model.n_tune: 2000` |
| **ESS < 400** | Not enough independent samples | Increase `n_samples` | `model.n_samples: 4000` |
| **All three bad** | Model is struggling hard | Increase everything | `target_accept: 0.99`, `n_tune: 3000`, `n_samples: 5000` |
| **Elasticity sign is wrong** (e.g., positive base price) | Data issue, not a sampling issue | Don't touch sampling — inspect `prepared_data.csv` | Check data paths, price columns, promo depth sign |
| **Credible intervals are very wide** | Not enough data or weak signal | More samples won't help much — consider informative priors or more data | `model.priors` or add more retailer data |

### Calibration Strategy

The order matters. Fix problems in this sequence:

```
Step 1: target_accept  (0.95 → 0.99)     ← fixes most divergences
Step 2: n_tune         (1000 → 2000/3000) ← gives sampler more warmup
Step 3: n_samples      (2000 → 4000)      ← only if CIs are too wide or ESS is low
```

> **Don't jump to Step 3 first.** If the sampler is taking bad steps (divergences), more samples just gives you more bad draws. Fix the step quality first.
>
> **Watch for divergences going UP with more samples.** This happened in our real runs (16 → 33 when doubling samples). It means the sampler is exploring more of the posterior and finding more trouble spots — the fix is more tuning, not more samples.

### Real-World Iteration Example

From actual runs on the Sparkling Ice analysis:

| Run | target_accept | n_tune | n_samples | Divergences | Action Taken |
|-----|--------------|--------|-----------|-------------|-------------|
| 1 | 0.95 | 1000 | 2000 | 61 | Raise target_accept |
| 2 | 0.99 | 1000 | 2000 | 18 | Raise n_tune |
| 3 | 0.99 | 2000 | 2000 | 16 | Try more samples |
| 4 | 0.99 | 2000 | 4000 | 33 | Divergences went UP — more samples isn't the fix. Raise n_tune further |
| 5 | 0.99 | 3000 | 4000 | ? | Pending |

**Lesson learned:** More samples without enough tuning can surface more divergences. Always prioritize `target_accept` → `n_tune` → `n_samples` in that order.

### Comparing Runs

After each iteration, compare the key estimates:

```bash
echo "=== Run 1 ===" && cat ./results/results_summary.csv
echo "=== Run 2 ===" && cat ./results_v2_tune2000/results_summary.csv
```

What you want to see: estimates are **stable across runs** (similar means and CIs). If raising `target_accept` dramatically changes the estimates, the original run was unreliable. If estimates barely move, the original run was fine — you're just cleaning up the convergence report.

### Keep a Run Log

`run_analysis.py` automatically appends to `run_log.txt` after every successful run. Each entry captures the timestamp, sampling params, output directory, and convergence metrics.

A typical `run_log.txt` looks like:

```
Run 1 | 2026-02-07 00:21 | tune=1000 samples=2000 target_accept=0.95 | output=results | Divergences: 61
Run 2 | 2026-02-07 00:31 | tune=1000 samples=2000 target_accept=0.99 | output=results (overwrote) | Divergences: 18
Run 3 | 2026-02-07 00:51 | tune=2000 samples=2000 target_accept=0.99 | output=results_v2_tune2000 | Divergences: 16
Run 4 | 2026-02-07 01:09 | tune=2000 samples=4000 target_accept=0.99 | output=results_v3_samples4000 | Divergences: 33
```

**View it anytime:**
```bash
cat run_log.txt
```

**Commit it to Git** so it's versioned with your repo:
```bash
git add run_log.txt && git commit -m "update run log" && git push
```

> If you need to manually add an entry (e.g., for a run before auto-logging was enabled):
> ```bash
> echo "Run N | $(date) | tune=X samples=Y target_accept=Z | output=DIR | $(grep -i 'divergen' ./DIR/model_summary.txt)" >> run_log.txt
> ```

This builds a history like:

```
Fri Feb  7 00:45 2026 | tune=1000 samples=2000 target_accept=0.95 | output=results           | notes: first run
  → Divergences: 61 (should be 0)
Fri Feb  7 01:10 2026 | tune=1000 samples=2000 target_accept=0.99 | output=results            | notes: raised target_accept
  → Divergences: 18 (should be 0)
Fri Feb  7 01:40 2026 | tune=2000 samples=2000 target_accept=0.99 | output=results_v2_tune2000 | notes: more tuning
  → Divergences: 0 (should be 0)
```

> **Tip:** Commit `run_log.txt` to Git so it's versioned with your code and results.

### Runtime Expectations

| Config | Approximate Runtime (16 vCPUs) |
|--------|-------------------------------|
| `samples: 2000, tune: 1000, chains: 4` | 3–5 min |
| `samples: 4000, tune: 2000, chains: 4` | 8–15 min |
| `samples: 5000, tune: 3000, chains: 4` | 15–25 min |

Higher `target_accept` (0.99 vs 0.95) adds ~20–40% to runtime.

### When Divergences Won't Hit Zero: Stability = Robustness

Sometimes, after multiple iterations of tuning, you still can't eliminate all divergences. **This doesn't necessarily mean your results are wrong.** The critical question is: **are the estimates stable across runs?**

Run this comparison across your iterations:

```bash
echo "=== Run 1 ===" && cat ./results/results_summary.csv
echo ""
echo "=== Run 3 ===" && cat ./results_v2_tune2000/results_summary.csv
echo ""
echo "=== Run 5 ===" && cat ./results_v4_tune3000/results_summary.csv
```

**If estimates are stable** (means and credible intervals barely move across runs with different sampling configs), your results are robust. The divergences are happening in a part of the posterior that doesn't affect the parameters you care about.

Real example from the Sparkling Ice analysis — 5 runs with divergences ranging from 16 to 61:

| Parameter | Run 1 (61 divs) | Run 5 (41 divs) | Stable? |
|-----------|-----------------|-----------------|---------|
| Base Price Elasticity | -1.827 [-2.717, -1.154] | -1.821 [-2.721, -1.154] | ✅ Yes |
| Promotional Elasticity | -4.247 [-4.839, -3.787] | -4.249 [-4.836, -3.792] | ✅ Yes |
| Cross-Price | -0.094 [-0.227, 0.042] | -0.094 [-0.229, 0.040] | ✅ Yes |
| Summer Seasonality | 0.197 [0.156, 0.238] | 0.197 [0.156, 0.238] | ✅ Yes |
| Time Trend | -0.001 [-0.001, -0.001] | -0.001 [-0.001, -0.001] | ✅ Yes |

**Verdict:** Estimates are virtually identical. Divergences are not affecting results. Safe to present.

**When presenting results with divergences, report it as:**

- R-hat: < 1.01 ✅
- ESS: > 400 ✅
- Estimates stable across N sampling configurations ✅
- Divergences present but do not affect parameter estimates

**If estimates are NOT stable** (means shift significantly or CIs widen/narrow dramatically between runs), the divergences are corrupting your results. In that case:

1. Inspect trace plots to identify which parameter is causing trouble
2. Consider reparameterizing the model
3. Check for data issues (outliers, near-zero variance in a feature, extreme collinearity)
4. As a last resort, consider simplifying the model (e.g., drop cross-price if it's causing instability)

> **Bottom line:** Zero divergences is the ideal. But in practice, **stable estimates across multiple runs** is what actually matters for decision-making. If 5 different sampling configs all give you the same answer, you can trust that answer.

---

## Viewing the HTML Report

**From Cursor:** Right-click `elasticity_report.html` → Open Preview

**Copy to your laptop (PowerShell on local machine):**
```powershell
scp -i C:/Users/<username>/.ssh/vm-mcmc-bayesian_key.pem `
  azureuser@<PUBLIC_IP>:/home/azureuser/tr-price-elasticity-bayesian/results/elasticity_report.html `
  C:/Users/<username>/Downloads/
```

Then open in your browser.

---

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `No such file or directory: venv312` | Wrong directory or venv not created | `cd` to repo root, run `bash ./scripts/setup_venv_py312_linux.sh` |
| `Volume Sales` column missing | Retailer (e.g., Costco) doesn't have it | Add `--volume-sales-factor Costco=2.0` or set in YAML |
| R-hat too high / divergences | Insufficient sampling | See **Decision Guide** above |
| MCMC job killed on disconnect | Not using tmux | Always run long jobs inside `tmux new -s mcmc` |
| `git push` fails on VM | HTTPS auth doesn't work headless | Switch to SSH remote (see One-Time Setup) |
| tmux session name already exists | Previous session still alive | `tmux kill-session -t mcmc` then create new, or use `mcmc2`, `mcmc3` |

---

## Reproducibility

To re-run and get comparable results:

- Keep `config_template.yaml` in version control (or save a copy per run)
- Save `prepared_data.csv` from each run
- Use a fixed seed: YAML `model.random_seed: 42`
- If you change sampling params, priors, or data filtering → **always use a new output directory**
- Name directories meaningfully: `results_v1_baseline`, `results_v2_target099`, etc.

### Going Back to a Previous Run

Every run's outputs are preserved in their own folder. **You never need to re-run to go back.** Just use the folder from the run you want.

Example — you did 5 runs and Run 3 had the best results:

```
./results/                    ← Run 1 (target_accept=0.95, 61 divergences)
./results_v2_tune2000/        ← Run 3 (tune=2000, 16 divergences)  ← USE THIS ONE
./results_v3_samples4000/     ← Run 4 (samples=4000, 33 divergences)
./results_v4_tune3000/        ← Run 5 (tune=3000, 41 divergences)
```

To use Run 3's results:
```bash
# View the report
cat ./results_v2_tune2000/results_summary.csv

# Copy the HTML report to your laptop
scp azureuser@<PUBLIC_IP>:/home/azureuser/tr-price-elasticity-bayesian/results_v2_tune2000/elasticity_report.html .
```

No re-running, no config changes. The HTML report, summary CSV, trace file, and plots are all already there.

> **This is why we never overwrite.** Each run is a snapshot. Use `run_log.txt` to find which folder had the best results, and just point to that folder.

---

## End of Session Checklist

Before you walk away:

```
1. Push your work       → git add -A && git commit -m "msg" && git push
2. Deallocate the VM    → Portal → Stop → confirm "Stopped (deallocated)"
```

**Deallocate via Azure Portal:**
1. Go to [portal.azure.com](https://portal.azure.com)
2. Search **"Virtual machines"** → click **vm-mcmc-bayesian**
3. Click **⏹ Stop** in the top toolbar
4. Confirm when prompted
5. **Wait and verify** status shows **"Stopped (deallocated)"**

**Or CLI:**
```bash
az vm deallocate --resource-group rg-bayesian-elasticity --name vm-mcmc-bayesian
```

> ⚠️ **If you skip this, the VM keeps billing.** Auto-shutdown at 11 PM is a safety net, not a plan.
