from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Tuple

import numpy as np
import pandas as pd
import arviz as az


RetailerName = str


CANONICAL_RETAILERS: List[RetailerName] = ["BJ's", "Costco", "Sam's Club"]


def _safe_unique_retailers(data: pd.DataFrame) -> List[RetailerName]:
    if not isinstance(data, pd.DataFrame) or "Retailer" not in data.columns:
        return []
    vals = [str(x) for x in data["Retailer"].dropna().unique().tolist()]
    # Prefer stable, business order when present.
    preferred = ["BJ's", "Costco", "Sam's Club", "BJs", "Sams", "Costco"]
    # Normalize common variants to canonical display.
    norm_map = {"BJs": "BJ's", "Sams": "Sam's Club"}
    canon = [norm_map.get(v, v) for v in vals]
    canon_unique = []
    for v in canon:
        if v not in canon_unique:
            canon_unique.append(v)
    # Order canon_unique by preferred where possible, then append any extras.
    preferred_canon = ["BJ's", "Costco", "Sam's Club"]
    ordered = [r for r in preferred_canon if r in canon_unique]
    for r in canon_unique:
        if r not in ordered:
            ordered.append(r)
    return ordered


def _get_group_index(results: Any, retailer: str) -> Optional[int]:
    groups = getattr(results, "groups", None)
    if groups is None:
        return None
    # groups can be list/Index-like
    groups_list = [str(g) for g in list(groups)]
    # normalize common variants
    norm_map = {"BJs": "BJ's", "Sams": "Sam's Club"}
    groups_list_norm = [norm_map.get(g, g) for g in groups_list]
    try:
        return groups_list_norm.index(retailer)
    except ValueError:
        return None


def _flatten_samples(x: np.ndarray) -> np.ndarray:
    return np.asarray(x).reshape(-1)


def _summary_from_samples(samples: np.ndarray) -> Dict[str, float]:
    s = _flatten_samples(samples)
    return {
        "mean": float(np.mean(s)),
        "median": float(np.median(s)),
        "sd": float(np.std(s, ddof=0)),
        "ci_lower": float(np.percentile(s, 2.5)),
        "ci_upper": float(np.percentile(s, 97.5)),
    }


def _prob_negative(samples: np.ndarray) -> float:
    s = _flatten_samples(samples)
    return float(np.mean(s < 0))


def _prob_abs_gt(samples: np.ndarray, threshold: float) -> float:
    s = _flatten_samples(samples)
    return float(np.mean(np.abs(s) > threshold))


def _get_posterior(results: Any):
    trace = getattr(results, "trace", None)
    if trace is None:
        raise ValueError("results.trace is required for report generation.")
    return trace.posterior


def _get_var_samples(results: Any, var: str) -> Optional[np.ndarray]:
    posterior = _get_posterior(results)
    if var not in posterior:
        return None
    return posterior[var].values


def _get_scalar_samples(results: Any, var: str) -> Optional[np.ndarray]:
    x = _get_var_samples(results, var)
    if x is None:
        return None
    return _flatten_samples(x)


def _get_group_samples(results: Any, var: str, retailer: str) -> Optional[np.ndarray]:
    posterior = _get_posterior(results)
    if var not in posterior:
        return None
    idx = _get_group_index(results, retailer)
    if idx is None:
        return None
    # Expect dims: (chain, draw, group)
    arr = posterior[var].values
    if arr.ndim < 3:
        return None
    return _flatten_samples(arr[:, :, idx])


def compute_evidence_table(
    data: pd.DataFrame,
    base_elasticity_by_retailer_mean: Mapping[str, float],
    *,
    pct_threshold: float = 1.0,
    window_weeks: int = 4,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Contract §3: Historical Price Change Evidence Table.
    """
    required = {"Retailer", "Date", "Base_Price_SI", "Volume_Sales_SI"}
    if not isinstance(data, pd.DataFrame) or not required.issubset(set(data.columns)):
        return [], {"events_total": 0, "events_qualified": 0, "skipped_insufficient_window": 0, "skipped_missing_values": 0}

    df = data.copy()
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values(["Retailer", "Date"])

    out: List[Dict[str, Any]] = []
    events_total = 0
    events_qualified = 0
    skipped_insufficient_window = 0
    skipped_missing_values = 0
    for retailer, g in df.groupby("Retailer", sort=False):
        r = str(retailer)
        if r not in base_elasticity_by_retailer_mean:
            continue
        elast = float(base_elasticity_by_retailer_mean[r])

        g = g.reset_index(drop=True)
        pc = g["Base_Price_SI"].pct_change() * 100.0
        events = pc.abs() > float(pct_threshold)
        idxs = np.where(events.fillna(False).values)[0]
        for i in idxs:
            events_total += 1
            # Need enough before/after window
            before_start = i - window_weeks
            after_end = i + window_weeks
            if before_start < 0 or after_end >= len(g):
                skipped_insufficient_window += 1
                continue

            before = g.loc[before_start : i - 1, "Volume_Sales_SI"].astype(float)
            after = g.loc[i : i + window_weeks - 1, "Volume_Sales_SI"].astype(float)
            if before.isna().all() or after.isna().all():
                skipped_missing_values += 1
                continue
            before_mean = float(before.mean())
            after_mean = float(after.mean())
            if before_mean == 0:
                skipped_missing_values += 1
                continue
            observed = (after_mean / before_mean - 1.0) * 100.0

            price_move = float(pc.iloc[i])
            predicted = elast * price_move

            diff = abs(observed - predicted)
            if diff <= 1.5:
                match = "Close"
            elif diff <= 3.0 and np.sign(observed) == np.sign(predicted):
                match = "Directional"
            else:
                match = "Poor"

            out.append(
                {
                    "Retailer": r,
                    "Date": g.loc[i, "Date"].date().isoformat(),
                    "Price_Move_Pct": price_move,
                    "Observed_Vol_Impact_Pct": observed,
                    "Predicted_Vol_Impact_Pct": predicted,
                    "Match": match,
                }
            )
            events_qualified += 1

    meta = {
        "events_total": int(events_total),
        "events_qualified": int(events_qualified),
        "skipped_insufficient_window": int(skipped_insufficient_window),
        "skipped_missing_values": int(skipped_missing_values),
        "pct_threshold": float(pct_threshold),
        "window_weeks": int(window_weeks),
    }
    return out, meta


def audit_results_vs_contract(results: Any) -> Dict[str, Any]:
    """
    Lightweight audit for planning/debugging: what key fields exist on `results`.
    """
    posterior = _get_posterior(results)
    fields = {
        "has_trace": getattr(results, "trace", None) is not None,
        "posterior_vars": sorted(list(posterior.data_vars)),
        "has_base_elasticity": getattr(results, "base_elasticity", None) is not None,
        "has_promo_elasticity": getattr(results, "promo_elasticity", None) is not None,
        "has_group_elasticities": hasattr(results, "group_base_elasticities") or hasattr(results, "group_elasticities"),
        "has_seasonality": bool(getattr(results, "seasonal_effects", None)),
        "has_time_trend": getattr(results, "beta_time_trend", None) is not None,
        "convergence": {
            "converged": getattr(results, "converged", None),
            "rhat_max": getattr(results, "rhat_max", None),
            "ess_min": getattr(results, "ess_min", None),
            "n_divergences": getattr(results, "n_divergences", None),
        },
    }
    return fields


def build_report_payload(
    results: Any,
    data: pd.DataFrame,
    *,
    include_plots: bool,
    plot_img_tags: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    """
    Build a JSON-serializable payload consumed by the HTML templates/JS.
    """
    retailers_in_data = _safe_unique_retailers(data)
    # Contract requirement: always show these retailers, even if missing in data.
    retailers = CANONICAL_RETAILERS[:]
    # If a non-canonical retailer appears in data, append it at the end (won't break templates).
    for r in retailers_in_data:
        if r not in retailers:
            retailers.append(r)
    is_hier = hasattr(results, "groups") and getattr(results, "groups", None) is not None
    posterior = _get_posterior(results)

    # Coefficient samples (overall + per retailer)
    coeffs: Dict[str, Dict[str, Any]] = {"base": {}, "promo": {}, "cross": {}}
    probs: Dict[str, Dict[str, Any]] = {"base": {}, "promo": {}, "cross": {}}
    summaries: Dict[str, Dict[str, Any]] = {"base": {}, "promo": {}, "cross": {}}

    # Overall samples: hierarchical uses mu_global_* when present; otherwise scalar base_elasticity
    base_overall = _get_scalar_samples(results, "mu_global_base") or _get_scalar_samples(results, "base_elasticity")
    promo_overall = _get_scalar_samples(results, "mu_global_promo") or _get_scalar_samples(results, "promo_elasticity")
    cross_overall = _get_scalar_samples(results, "elasticity_cross")

    if base_overall is not None:
        summaries["base"]["Overall"] = _summary_from_samples(base_overall)
        probs["base"]["Overall"] = {
            "p_negative": _prob_negative(base_overall),
            "p_elastic_abs_gt_1": _prob_abs_gt(base_overall, 1.0),
        }
        coeffs["base"]["Overall"] = float(summaries["base"]["Overall"]["mean"])

    if promo_overall is not None:
        summaries["promo"]["Overall"] = _summary_from_samples(promo_overall)
        probs["promo"]["Overall"] = {"p_negative": _prob_negative(promo_overall)}
        coeffs["promo"]["Overall"] = float(summaries["promo"]["Overall"]["mean"])

    if cross_overall is not None:
        summaries["cross"]["Overall"] = _summary_from_samples(cross_overall)
        probs["cross"]["Overall"] = {"p_positive": float(np.mean(_flatten_samples(cross_overall) > 0))}
        coeffs["cross"]["Overall"] = float(summaries["cross"]["Overall"]["mean"])

    # Retailer-specific (hierarchical) or shared fallback
    base_by_retailer_mean: Dict[str, float] = {}
    promo_by_retailer_mean: Dict[str, float] = {}
    base_by_retailer_samples: Dict[str, np.ndarray] = {}
    promo_by_retailer_samples: Dict[str, np.ndarray] = {}
    for r in retailers:
        base_s = _get_group_samples(results, "base_elasticity", r)
        promo_s = _get_group_samples(results, "promo_elasticity", r)

        if base_s is not None:
            summaries["base"][r] = _summary_from_samples(base_s)
            probs["base"][r] = {
                "p_negative": _prob_negative(base_s),
                "p_elastic_abs_gt_1": _prob_abs_gt(base_s, 1.0),
            }
            coeffs["base"][r] = float(summaries["base"][r]["mean"])
            base_by_retailer_mean[r] = float(summaries["base"][r]["mean"])
            base_by_retailer_samples[r] = _flatten_samples(base_s)
        elif "Overall" in summaries["base"]:
            # SHARED fallback: copy overall estimate
            summaries["base"][r] = dict(summaries["base"]["Overall"])
            probs["base"][r] = dict(probs["base"]["Overall"])
            coeffs["base"][r] = float(coeffs["base"]["Overall"])
            base_by_retailer_mean[r] = float(coeffs["base"]["Overall"])
            base_by_retailer_samples[r] = _flatten_samples(base_overall) if base_overall is not None else np.array([])

        if promo_s is not None:
            summaries["promo"][r] = _summary_from_samples(promo_s)
            probs["promo"][r] = {"p_negative": _prob_negative(promo_s)}
            coeffs["promo"][r] = float(summaries["promo"][r]["mean"])
            promo_by_retailer_mean[r] = float(summaries["promo"][r]["mean"])
            promo_by_retailer_samples[r] = _flatten_samples(promo_s)
        elif "Overall" in summaries["promo"]:
            summaries["promo"][r] = dict(summaries["promo"]["Overall"])
            probs["promo"][r] = dict(probs["promo"]["Overall"])
            coeffs["promo"][r] = float(coeffs["promo"]["Overall"])
            promo_by_retailer_mean[r] = float(coeffs["promo"]["Overall"])
            promo_by_retailer_samples[r] = _flatten_samples(promo_overall) if promo_overall is not None else np.array([])

    # Seasonal effects (shared)
    seasonal_effects = getattr(results, "seasonal_effects", {}) or {}
    seasonal = {}
    for k, v in seasonal_effects.items():
        seasonal[str(k)] = {
            "mean": float(v.mean),
            "ci_lower": float(v.ci_lower),
            "ci_upper": float(v.ci_upper),
        }

    # Time trend (shared)
    beta_time = getattr(results, "beta_time_trend", None)
    beta_time_obj = None
    if beta_time is not None:
        beta_time_obj = {
            "mean": float(beta_time.mean),
            "ci_lower": float(beta_time.ci_lower),
            "ci_upper": float(beta_time.ci_upper),
            "annual_pct_mean": float((np.exp(beta_time.mean * 52) - 1) * 100),
            "annual_pct_ci_lower": float((np.exp(beta_time.ci_lower * 52) - 1) * 100),
            "annual_pct_ci_upper": float((np.exp(beta_time.ci_upper * 52) - 1) * 100),
        }

    # Convergence diagnostics (summary table)
    diag = {
        "converged": getattr(results, "converged", None),
        "rhat_max": getattr(results, "rhat_max", None),
        "ess_min": getattr(results, "ess_min", None),
        "n_divergences": getattr(results, "n_divergences", None),
    }
    az_sum = az.summary(results.trace, round_to=None)
    # Normalize column names across arviz versions
    rhat_col = "r_hat" if "r_hat" in az_sum.columns else ("rhat" if "rhat" in az_sum.columns else None)
    essb_col = "ess_bulk" if "ess_bulk" in az_sum.columns else None
    esst_col = "ess_tail" if "ess_tail" in az_sum.columns else None

    diag_rows = []
    for param, row in az_sum.iterrows():
        diag_rows.append(
            {
                "param": str(param),
                "rhat": float(row[rhat_col]) if rhat_col and pd.notna(row.get(rhat_col)) else None,
                "ess_bulk": float(row[essb_col]) if essb_col and pd.notna(row.get(essb_col)) else None,
                "ess_tail": float(row[esst_col]) if esst_col and pd.notna(row.get(esst_col)) else None,
            }
        )

    # Availability table from data flags
    availability = []
    if isinstance(data, pd.DataFrame) and "Retailer" in data.columns:
        cols = [c for c in ["has_promo", "has_competitor"] if c in data.columns]
        if cols:
            avail = data.groupby("Retailer")[cols].max(numeric_only=True).reset_index()
            for _, r in avail.iterrows():
                retailer = str(r["Retailer"])
                availability.append(
                    {
                        "Retailer": retailer,
                        "has_promo": int(r["has_promo"]) if "has_promo" in cols and pd.notna(r.get("has_promo")) else None,
                        "has_competitor": int(r["has_competitor"]) if "has_competitor" in cols and pd.notna(r.get("has_competitor")) else None,
                    }
                )

    # Evidence table (business report)
    evidence, evidence_meta = compute_evidence_table(data, base_by_retailer_mean)

    # Scenario grids (overall + by retailer)
    base_scenarios = [-5, -3, -1, 1, 3, 5]
    promo_scenarios = [5, 10, 15, 20]

    base_impacts = []
    for nm in ["Overall"] + retailers:
        s = base_by_retailer_samples.get(nm) if nm != "Overall" else (_flatten_samples(base_overall) if base_overall is not None else None)
        if s is None or len(s) == 0:
            continue
        for pct in base_scenarios:
            vol = s * float(pct)
            rev = ((1 + vol / 100.0) * (1 + float(pct) / 100.0) - 1) * 100.0
            base_impacts.append(
                {
                    "Retailer": nm,
                    "price_change_pct": float(pct),
                    "volume_impact_mean": float(np.mean(vol)),
                    "volume_impact_ci_lower": float(np.percentile(vol, 2.5)),
                    "volume_impact_ci_upper": float(np.percentile(vol, 97.5)),
                    "revenue_impact_mean": float(np.mean(rev)),
                    "revenue_impact_ci_lower": float(np.percentile(rev, 2.5)),
                    "revenue_impact_ci_upper": float(np.percentile(rev, 97.5)),
                    "probability_positive": float(np.mean(rev > 0)),
                }
            )

    promo_impacts = []
    if promo_overall is not None:
        for nm in ["Overall"] + retailers:
            s = promo_by_retailer_samples.get(nm) if nm != "Overall" else _flatten_samples(promo_overall)
            if s is None or len(s) == 0:
                continue
            for disc in promo_scenarios:
                depth = -abs(float(disc)) / 100.0
                vol = (np.exp(s * depth) - 1.0) * 100.0
                rev = ((1 + vol / 100.0) * (1 - abs(float(disc)) / 100.0) - 1) * 100.0
                promo_impacts.append(
                    {
                        "Retailer": nm,
                        "discount_depth_pct": float(disc),
                        "volume_impact_mean": float(np.mean(vol)),
                        "volume_impact_ci_lower": float(np.percentile(vol, 2.5)),
                        "volume_impact_ci_upper": float(np.percentile(vol, 97.5)),
                        "revenue_impact_mean": float(np.mean(rev)),
                        "revenue_impact_ci_lower": float(np.percentile(rev, 2.5)),
                        "revenue_impact_ci_upper": float(np.percentile(rev, 97.5)),
                        "probability_positive": float(np.mean(rev > 0)),
                    }
                )

    payload: Dict[str, Any] = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "model_type": "Hierarchical" if is_hier else "Simple",
        "n_obs": int(len(data)) if isinstance(data, pd.DataFrame) else None,
        "retailers": ["Overall"] + retailers,
        "coefficients": {
            "base": {k: float(v) for k, v in coeffs["base"].items()},
            "promo": {k: float(v) for k, v in coeffs["promo"].items()} if coeffs["promo"] else {},
            "cross": {k: float(v) for k, v in coeffs["cross"].items()} if coeffs["cross"] else {},
        },
        "summaries": summaries,
        "probabilities": probs,
        "seasonal": seasonal,
        "beta_time": beta_time_obj,
        "diagnostics": diag,
        "diagnostic_rows": diag_rows,
        "availability": availability,
        "evidence": evidence,
        "evidence_meta": evidence_meta,
        "scenarios": {
            "base": base_impacts,
            "promo": promo_impacts,
        },
    }

    if include_plots and plot_img_tags:
        payload["plots"] = dict(plot_img_tags)

    return payload

