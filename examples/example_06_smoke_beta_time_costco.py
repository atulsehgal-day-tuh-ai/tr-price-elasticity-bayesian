"""
Example 06: Smoke Test (Costco + beta_time + HTML report)

Why this exists
---------------
This is a single end-to-end "trust but verify" run intended to catch breakages after
recent pipeline/model changes:

- Costco CRX schema handling (heterogeneous retailer file)
- Volume Sales dependent variable behavior (including the Costco factor fallback)
- Time trend wiring: Week_Number -> beta_time -> beta_time_trend summary
- Report generation wiring (including time_trend_plot.png)

It is NOT meant to produce final inference-quality results. It runs tiny sampling
settings to validate that the plumbing works.

Run:
  python examples/example_06_smoke_beta_time_costco.py
"""

from __future__ import annotations

import os
import sys
import multiprocessing as mp
from pathlib import Path
from typing import Iterable, Optional

import yaml
import numpy as np

# Allow running this file directly: `python examples/example_06_smoke_beta_time_costco.py`
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data_prep import ElasticityDataPrep, PrepConfig
from bayesian_models import HierarchicalBayesianModel
from visualizations import generate_html_report


def _require_files(paths: Iterable[Path]) -> None:
    missing = [p for p in paths if not p.exists()]
    if missing:
        raise FileNotFoundError(
            "Missing required input CSV(s). Expected files:\n"
            + "\n".join([f"  - {p}" for p in paths])
            + "\n\nPlace your retailer files in the repo's data/ folder (see README.md)."
        )


def _require_cols(df, cols: Iterable[str], label: str = "DataFrame") -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise AssertionError(f"{label} is missing required columns: {missing}")


def _load_contracts() -> Optional[dict]:
    """
    Load retailer_data_contracts from config_template.yaml.
    This is important for Costco because it uses different skiprows/columns than Circana.
    """
    cfg_path = REPO_ROOT / "config_template.yaml"
    if not cfg_path.exists():
        return None

    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    return (cfg.get("data") or {}).get("retailer_data_contracts")


def main() -> None:
    print("=" * 80)
    print("EXAMPLE 06: SMOKE TEST (COSTCO + TIME TREND + HTML REPORT)")
    print("=" * 80)

    # ------------------------------------------------------------------------
    # STEP 0: INPUTS (Costco is REQUIRED for this smoke test)
    # ------------------------------------------------------------------------
    data_dir = REPO_ROOT / "data"
    bjs_csv = data_dir / "bjs.csv"
    sams_csv = data_dir / "sams.csv"
    costco_csv = data_dir / "costco.csv"
    _require_files([bjs_csv, sams_csv, costco_csv])

    # ------------------------------------------------------------------------
    # STEP 1: DATA PREP (explicitly includes Costco + stable Week_Number)
    # ------------------------------------------------------------------------
    retailer_config = {
        "BJs": {"has_promo": True, "has_competitor": True},
        "Sams": {"has_promo": True, "has_competitor": True},
        # Costco: no private label / competitor rows in CRX extract (mask in model)
        "Costco": {"has_promo": True, "has_competitor": False},
    }

    contracts = _load_contracts()
    if contracts is None:
        raise FileNotFoundError(
            "Expected config_template.yaml to exist so this smoke test can load "
            "retailer_data_contracts (needed to parse Costco correctly)."
        )

    prep = ElasticityDataPrep(
        PrepConfig(
            retailer_filter="All",
            include_seasonality=True,
            include_promotions=True,
            include_time_trend=True,
            # Keep Week_Number stable even if retailers have different start dates.
            week_number_origin_date="2023-01-01",
            separate_base_promo=True,
            # Costco Volume Sales fallback (if missing): Volume Sales = Unit Sales * 2.0
            volume_sales_factor_by_retailer={"Costco": 2.0},
            retailers=retailer_config,
            retailer_data_contracts=contracts,
            verbose=True,
        )
    )

    df = prep.transform(
        bjs_path=str(bjs_csv),
        sams_path=str(sams_csv),
        costco_path=str(costco_csv),
    )

    print(f"\nPrepared data: {df.shape[0]} rows x {df.shape[1]} cols")
    if "Retailer" in df.columns:
        print(f"Retailers: {sorted(df['Retailer'].unique().tolist())}")

    # ------------------------------------------------------------------------
    # STEP 2: PLUMBING ASSERTIONS (fast fail if anything regressed)
    # ------------------------------------------------------------------------
    _require_cols(df, ["Date", "Retailer", "Week_Number"], label="Prepared data")

    # Dependent variable (Volume DV) should exist in V2
    _require_cols(df, ["Log_Volume_Sales_SI"], label="Prepared data")

    # Core price feature should exist (at least one of these depending on path)
    if ("Log_Price_SI" not in df.columns) and ("Log_Base_Price_SI" not in df.columns):
        raise AssertionError("Prepared data missing both Log_Price_SI and Log_Base_Price_SI")

    week = df["Week_Number"].astype(float).values
    if not np.isfinite(week).all():
        raise AssertionError("Week_Number contains non-finite values")

    if (df["Retailer"].astype(str).str.lower() == "costco").sum() == 0:
        raise AssertionError("Expected Costco rows to be present in the prepared dataset")

    # ------------------------------------------------------------------------
    # STEP 3: FIT HIERARCHICAL MODEL (tiny MCMC: wiring validation only)
    # ------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("FITTING HIERARCHICAL MODEL (TINY MCMC: SMOKE TEST)")
    print("=" * 80)

    # NOTE: We intentionally keep this small. Convergence is not the goal here.
    model = HierarchicalBayesianModel(
        priors="default",
        n_samples=200,
        n_tune=200,
        n_chains=2,
        target_accept=0.90,
        random_seed=42,
        verbose=True,
    )

    results = model.fit(df)

    # Time trend must be extracted if beta_time is in the model/trace
    if getattr(results, "beta_time_trend", None) is None:
        raise AssertionError("Expected beta_time_trend to be present on results (include_time_trend=True).")

    beta_mean = float(results.beta_time_trend.mean)
    annual_pct = (np.exp(beta_mean * 52) - 1) * 100
    print(f"\nbeta_time mean (weekly): {beta_mean:.6f}")
    print(f"Annualized implied trend: {annual_pct:+.2f}%")

    # ------------------------------------------------------------------------
    # STEP 4: GENERATE HTML REPORT (ensures plotting/report wiring)
    # ------------------------------------------------------------------------
    out_dir = REPO_ROOT / "output_example_06"
    out_dir.mkdir(parents=True, exist_ok=True)

    report_path = generate_html_report(
        results=results,
        data=df,
        output_dir=str(out_dir),
        report_name="smoke_beta_time_costco_report.html",
    )

    report_file = Path(report_path)
    if not report_file.exists():
        raise FileNotFoundError(f"Expected HTML report to be written, but it does not exist: {report_file}")

    time_trend_plot = out_dir / "time_trend_plot.png"
    if not time_trend_plot.exists():
        raise FileNotFoundError(
            f"Expected time trend plot to be written (beta_time_trend present), but it does not exist: {time_trend_plot}"
        )

    print("\n" + "=" * 80)
    print("✓ EXAMPLE 06 COMPLETE")
    print("=" * 80)
    print(f"✓ HTML report: {report_file}")
    print(f"✓ Time trend plot: {time_trend_plot}")


if __name__ == "__main__":
    # Required for Windows multiprocessing safety in some environments
    mp.freeze_support()

    # Optional: ensure scientific libs don't over-thread on big VMs
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("MKL_NUM_THREADS", "1")
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

    main()

