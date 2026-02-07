"""
Example 07: VM Smoke Test — Generate Contract-Driven Reports from Existing Artifacts (NO MCMC)

Purpose
-------
When you SSH into the Azure VM, you often want a *fast* verification that the latest
reporting changes work, without spending time on sampling.

This script:
- Loads an existing `trace.nc` (ArviZ InferenceData) from a prior run
- Loads the corresponding `prepared_data.csv`
- Reconstructs a Results object (HierarchicalResults or BayesianResults)
- Generates the two contract-driven HTML reports:
    - statistical_validation_report.html
    - business_decision_brief.html

No MCMC is executed.

Run (example):
-------------
python examples/example_07_vm_smoke_generate_reports_from_artifacts.py --results-dir ./results_v4_tune3000
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import arviz as az
import pandas as pd

# Allow running this file directly: `python examples/...`
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from bayesian_models import BayesianResults, HierarchicalResults
from visualizations import generate_business_report, generate_statistical_report


def _canonicalize_group_name(name: str) -> str:
    s = str(name)
    if s == "BJs":
        return "BJ's"
    if s == "Sams":
        return "Sam's Club"
    return s


def _infer_group_order_from_prepared_data(df: pd.DataFrame) -> list[str]:
    """
    Match the group-indexing used during model build:
      group_idx = pd.Categorical(data['Retailer']).codes

    Pandas Categorical categories are sorted, so we mirror that here to ensure
    posterior group indices map to the correct retailer labels.
    """
    if "Retailer" not in df.columns:
        return []
    cats = list(pd.Categorical(df["Retailer"].astype(str)).categories)
    return [_canonicalize_group_name(x) for x in cats]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate reports from existing trace.nc + prepared_data.csv (no MCMC)")
    p.add_argument(
        "--results-dir",
        required=True,
        help="Path to a previous run output directory containing trace.nc and prepared_data.csv",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    results_dir = Path(args.results_dir).resolve()

    trace_path = results_dir / "trace.nc"
    data_path = results_dir / "prepared_data.csv"

    if not trace_path.exists():
        raise FileNotFoundError(f"Missing trace file: {trace_path}")
    if not data_path.exists():
        raise FileNotFoundError(f"Missing prepared data: {data_path}")

    print("=" * 80)
    print("EXAMPLE 07: REPORT SMOKE TEST (NO MCMC)")
    print("=" * 80)
    print(f"Results dir: {results_dir}")
    print(f"Trace: {trace_path.name}")
    print(f"Data:  {data_path.name}")

    df = pd.read_csv(data_path)
    idata = az.from_netcdf(trace_path)

    # Determine if the trace looks hierarchical by presence of group-shaped variables
    posterior_vars = set(list(idata.posterior.data_vars))
    is_hier = "base_elasticity" in posterior_vars and any(k.endswith("_dim_0") for k in idata.posterior.dims.keys())

    if is_hier:
        groups = _infer_group_order_from_prepared_data(df)
        if not groups:
            raise ValueError("Could not infer retailer groups from prepared_data.csv (missing Retailer column).")

        results = HierarchicalResults(
            trace=idata,
            model=None,
            data=df,
            config={"loaded_from": str(trace_path)},
            priors={},
            groups=groups,
        )
        print(f"Detected hierarchical trace. Groups: {groups}")
    else:
        results = BayesianResults(
            trace=idata,
            model=None,
            data=df,
            config={"loaded_from": str(trace_path)},
            priors={},
        )
        print("Detected simple trace (non-hierarchical).")

    # Generate contract-driven reports into the same results directory
    stat_path = generate_statistical_report(results=results, data=df, output_dir=str(results_dir))
    biz_path = generate_business_report(results=results, data=df, output_dir=str(results_dir))

    print("\n✓ Reports generated (no MCMC):")
    print(f"  - Statistical Validation Report: {stat_path}")
    print(f"  - Business Decision Brief:       {biz_path}")


if __name__ == "__main__":
    main()

