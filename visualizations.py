"""
Visualization Module for Bayesian Elasticity Analysis

Complete visualization suite including:
- MCMC trace plots (convergence diagnostics)
- Posterior distribution plots
- Seasonal pattern visualizations
- Revenue scenario plots
- Model comparison plots
- HTML report generation

Usage:
    from visualizations import generate_html_report
    
    generate_html_report(results, output_dir='./output')
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from typing import Optional, List, Dict
import arviz as az
from datetime import datetime

# Set style
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (12, 8)
plt.rcParams['font.size'] = 10


# ============================================================================
# TRACE PLOTS (MCMC DIAGNOSTICS)
# ============================================================================

def plot_trace(results, output_path: Optional[str] = None, figsize=(14, 10)):
    """
    Plot MCMC trace diagnostics
    
    Shows:
    - Trace plots (time series of samples)
    - Posterior distributions
    - Convergence assessment
    
    Parameters:
    ----------
    results : BayesianResults
        Results object from model fitting
    
    output_path : str, optional
        Path to save plot
    
    Returns:
    -------
    matplotlib.figure.Figure
    """
    
    # Select key parameters to plot
    if 'base_elasticity' in results.trace.posterior:
        var_names = ['base_elasticity', 'promo_elasticity', 'elasticity_cross']
    else:
        var_names = ['elasticity_own', 'elasticity_cross']
    
    # Legacy promo effect (V1)
    if 'beta_promo' in results.trace.posterior and 'promo_elasticity' not in results.trace.posterior:
        var_names.append('beta_promo')
    
    if 'beta_spring' in results.trace.posterior:
        var_names.extend(['beta_spring', 'beta_summer', 'beta_fall'])
    
    # Create trace plot using ArviZ
    axes = az.plot_trace(
        results.trace,
        var_names=var_names,
        figsize=figsize,
        compact=False
    )
    
    plt.suptitle('MCMC Trace Plots', fontsize=16, fontweight='bold', y=1.00)
    plt.tight_layout()
    
    if output_path:
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"Trace plot saved to {output_path}")
    
    return plt.gcf()


# ============================================================================
# POSTERIOR DISTRIBUTIONS
# ============================================================================

def plot_posteriors(results, output_path: Optional[str] = None, figsize=(14, 10)):
    """
    Plot posterior distributions for all parameters
    
    Shows:
    - Histogram of posterior samples
    - Credible intervals
    - Prior distributions (for comparison)
    
    Parameters:
    ----------
    results : BayesianResults
        Results object
    
    output_path : str, optional
        Path to save plot
    
    Returns:
    -------
    matplotlib.figure.Figure
    """
    
    # Determine parameters to plot
    params = []
    titles = []
    
    # V2: base vs promo elasticities (preferred)
    if hasattr(results, 'base_elasticity') and results.base_elasticity is not None:
        params.append(('base_elasticity', results.base_elasticity))
        titles.append('Base Price Elasticity')

        if getattr(results, 'promo_elasticity', None) is not None:
            params.append(('promo_elasticity', results.promo_elasticity))
            titles.append('Promotional Elasticity')
    elif results.elasticity_own:
        params.append(('elasticity_own', results.elasticity_own))
        titles.append('Own-Price Elasticity')
    
    if results.elasticity_cross:
        params.append(('elasticity_cross', results.elasticity_cross))
        titles.append('Cross-Price Elasticity')
    
    # Legacy promo effect (V1) only if promo elasticity is not present
    if results.beta_promo and getattr(results, 'promo_elasticity', None) is None:
        params.append(('beta_promo', results.beta_promo))
        titles.append('Promotional Effect')
    
    for season, summary in results.seasonal_effects.items():
        params.append((f'beta_{season.lower()}', summary))
        titles.append(f'{season} Effect')
    
    # Create subplots
    n_params = len(params)
    n_cols = 3
    n_rows = (n_params + n_cols - 1) // n_cols
    
    fig, axes = plt.subplots(n_rows, n_cols, figsize=figsize)
    axes = axes.flatten() if n_params > 1 else [axes]
    
    for idx, ((param_name, summary), title) in enumerate(zip(params, titles)):
        ax = axes[idx]
        
        # Get samples
        samples = results.trace.posterior[param_name].values.flatten()
        
        # Plot histogram
        ax.hist(samples, bins=50, density=True, alpha=0.6, color='steelblue', edgecolor='black')
        
        # Add vertical lines for mean and credible interval
        ax.axvline(summary.mean, color='red', linestyle='--', linewidth=2, label=f'Mean: {summary.mean:.3f}')
        ax.axvline(summary.ci_lower, color='green', linestyle=':', linewidth=1.5, label=f'95% CI: [{summary.ci_lower:.3f}, {summary.ci_upper:.3f}]')
        ax.axvline(summary.ci_upper, color='green', linestyle=':', linewidth=1.5)
        
        ax.set_title(title, fontweight='bold')
        ax.set_xlabel('Value')
        ax.set_ylabel('Density')
        ax.legend(fontsize=8)
        ax.grid(alpha=0.3)
    
    # Hide unused subplots
    for idx in range(n_params, len(axes)):
        axes[idx].axis('off')
    
    plt.suptitle('Posterior Distributions', fontsize=16, fontweight='bold')
    plt.tight_layout()
    
    if output_path:
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"Posterior plot saved to {output_path}")
    
    return fig


# ============================================================================
# SEASONAL PATTERNS
# ============================================================================

def plot_seasonal_patterns(results, data, output_path: Optional[str] = None, figsize=(12, 6)):
    """
    Plot seasonal sales patterns
    
    Shows:
    - Monthly average sales
    - Seasonal effects with uncertainty
    
    Parameters:
    ----------
    results : BayesianResults
        Results object
    
    data : pd.DataFrame
        Original data
    
    output_path : str, optional
        Path to save plot
    
    Returns:
    -------
    matplotlib.figure.Figure
    """
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=figsize)
    
    # Plot 1: Monthly sales patterns
    # Prefer Volume Sales (normalized consumption) if available; fall back to Unit Sales for backward compatibility.
    sales_col = None
    ylabel = None
    if 'Volume_Sales_SI' in data.columns:
        sales_col = 'Volume_Sales_SI'
        ylabel = 'Average Volume Sales'
    elif 'Unit_Sales_SI' in data.columns:
        sales_col = 'Unit_Sales_SI'
        ylabel = 'Average Unit Sales'

    if 'Date' in data.columns and sales_col is not None:
        monthly_data = data.copy()
        monthly_data['Month'] = pd.to_datetime(monthly_data['Date']).dt.month
        monthly_avg = monthly_data.groupby('Month')[sales_col].mean()
        
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        
        ax1.bar(range(1, 13), monthly_avg.values, color='steelblue', alpha=0.7, edgecolor='black')
        ax1.set_xticks(range(1, 13))
        ax1.set_xticklabels(months, rotation=45)
        ax1.set_xlabel('Month')
        ax1.set_ylabel(ylabel)
        ax1.set_title('Monthly Sales Pattern', fontweight='bold')
        ax1.grid(alpha=0.3, axis='y')
    
    # Plot 2: Seasonal effects from model
    if results.seasonal_effects:
        seasons = list(results.seasonal_effects.keys())
        means = [results.seasonal_effects[s].mean for s in seasons]
        ci_lower = [results.seasonal_effects[s].ci_lower for s in seasons]
        ci_upper = [results.seasonal_effects[s].ci_upper for s in seasons]
        
        # Convert to percentage lift
        means_pct = [(np.exp(m) - 1) * 100 for m in means]
        ci_lower_pct = [(np.exp(l) - 1) * 100 for l in ci_lower]
        ci_upper_pct = [(np.exp(u) - 1) * 100 for u in ci_upper]
        
        x_pos = np.arange(len(seasons))
        
        ax2.bar(x_pos, means_pct, color='coral', alpha=0.7, edgecolor='black')
        ax2.errorbar(x_pos, means_pct, 
                    yerr=[np.array(means_pct) - np.array(ci_lower_pct),
                          np.array(ci_upper_pct) - np.array(means_pct)],
                    fmt='none', color='black', capsize=5)
        
        ax2.axhline(0, color='black', linestyle='--', linewidth=1)
        ax2.set_xticks(x_pos)
        ax2.set_xticklabels(seasons)
        ax2.set_xlabel('Season')
        ax2.set_ylabel('Sales Lift vs Winter (%)')
        ax2.set_title('Seasonal Effects (vs Winter Baseline)', fontweight='bold')
        ax2.grid(alpha=0.3, axis='y')
    
    plt.tight_layout()
    
    if output_path:
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"Seasonal plot saved to {output_path}")
    
    return fig


# ============================================================================
# REVENUE SCENARIOS
# ============================================================================

def plot_base_vs_promo_comparison(results, output_path: Optional[str] = None, figsize=(10, 5)):
    """
    Plot base price elasticity vs promotional elasticity side-by-side (V2).

    Output: base_vs_promo_comparison.png
    """
    if getattr(results, 'promo_elasticity', None) is None:
        print("Promotional elasticity not available - skipping base vs promo comparison")
        return None

    base = results.base_elasticity
    promo = results.promo_elasticity

    labels = ["Base", "Promo"]
    means = [base.mean, promo.mean]
    ci_lower = [base.ci_lower, promo.ci_lower]
    ci_upper = [base.ci_upper, promo.ci_upper]

    yerr = [
        np.array(means) - np.array(ci_lower),
        np.array(ci_upper) - np.array(means),
    ]

    fig, ax = plt.subplots(1, 1, figsize=figsize)
    ax.bar(labels, means, color=["steelblue", "coral"], alpha=0.8, edgecolor="black")
    ax.errorbar(labels, means, yerr=yerr, fmt="none", color="black", capsize=6)
    ax.axhline(0, color="black", linestyle="--", linewidth=1, alpha=0.6)

    ax.set_title("Base vs Promotional Elasticity", fontweight="bold")
    ax.set_ylabel("Elasticity (log sales response)")
    ax.grid(alpha=0.25, axis="y")

    # Annotate magnitude ratio
    try:
        ratio = abs(promo.mean) / max(abs(base.mean), 1e-9)
        ax.text(0.5, 0.95, f"|Promo| / |Base| ≈ {ratio:.1f}x", transform=ax.transAxes,
                ha="center", va="top")
    except Exception:
        pass

    plt.tight_layout()

    if output_path:
        plt.savefig(output_path, dpi=300, bbox_inches="tight")
        print(f"Base vs promo comparison saved to {output_path}")

    return fig


def plot_revenue_scenarios_base(results, scenarios=None, output_path: Optional[str] = None, figsize=(12, 8)):
    """
    Plot revenue impact scenarios for base price changes (V2).

    Output: revenue_scenarios_base.png
    """
    if scenarios is None:
        scenarios = [-5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5]

    impacts = [results.base_price_impact(s) for s in scenarios]

    means = [i['revenue_impact_mean'] for i in impacts]
    ci_lower = [i['revenue_impact_ci'][0] for i in impacts]
    ci_upper = [i['revenue_impact_ci'][1] for i in impacts]
    probs = [i['probability_positive'] for i in impacts]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=figsize)

    ax1.plot(scenarios, means, 'o-', color='steelblue', linewidth=2, markersize=8, label='Expected Impact')
    ax1.fill_between(scenarios, ci_lower, ci_upper, alpha=0.3, color='steelblue', label='95% Credible Interval')
    ax1.axhline(0, color='red', linestyle='--', linewidth=1, alpha=0.5)
    ax1.axvline(0, color='gray', linestyle='--', linewidth=1, alpha=0.5)

    ax1.set_xlabel('Base Price Change (%)', fontsize=12)
    ax1.set_ylabel('Revenue Impact (%)', fontsize=12)
    ax1.set_title('Revenue Impact of Base Price Changes', fontweight='bold', fontsize=14)
    ax1.legend()
    ax1.grid(alpha=0.3)

    colors = ['green' if p >= 0.5 else 'red' for p in probs]
    ax2.bar(scenarios, [p * 100 for p in probs], color=colors, alpha=0.7, edgecolor='black')
    ax2.axhline(50, color='black', linestyle='--', linewidth=1, alpha=0.5)

    ax2.set_xlabel('Base Price Change (%)', fontsize=12)
    ax2.set_ylabel('Probability of Positive Revenue Impact (%)', fontsize=12)
    ax2.set_title('Probability of Revenue Increase (Base Price)', fontweight='bold', fontsize=14)
    ax2.grid(alpha=0.3, axis='y')

    plt.tight_layout()

    if output_path:
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"Base price scenarios plot saved to {output_path}")

    return fig


def plot_revenue_scenarios_promo(results, discounts=None, output_path: Optional[str] = None, figsize=(12, 8)):
    """
    Plot revenue impact scenarios for promotional discounts (V2).

    Output: revenue_scenarios_promo.png
    """
    if getattr(results, 'promo_elasticity', None) is None:
        print("Promotional elasticity not available - skipping promo scenarios")
        return None

    if discounts is None:
        discounts = [5, 10, 15, 20]

    impacts = [results.promo_impact(d) for d in discounts]

    means = [i['revenue_impact_mean'] for i in impacts]
    ci_lower = [i['revenue_impact_ci'][0] for i in impacts]
    ci_upper = [i['revenue_impact_ci'][1] for i in impacts]
    probs = [i['probability_positive'] for i in impacts]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=figsize)

    ax1.plot(discounts, means, 'o-', color='coral', linewidth=2, markersize=8, label='Expected Impact')
    ax1.fill_between(discounts, ci_lower, ci_upper, alpha=0.3, color='coral', label='95% Credible Interval')
    ax1.axhline(0, color='red', linestyle='--', linewidth=1, alpha=0.5)

    ax1.set_xlabel('Discount Depth (%)', fontsize=12)
    ax1.set_ylabel('Revenue Impact (%)', fontsize=12)
    ax1.set_title('Revenue Impact of Promotional Discounts', fontweight='bold', fontsize=14)
    ax1.legend()
    ax1.grid(alpha=0.3)

    colors = ['green' if p >= 0.5 else 'red' for p in probs]
    ax2.bar(discounts, [p * 100 for p in probs], color=colors, alpha=0.7, edgecolor='black')
    ax2.axhline(50, color='black', linestyle='--', linewidth=1, alpha=0.5)

    ax2.set_xlabel('Discount Depth (%)', fontsize=12)
    ax2.set_ylabel('Probability of Positive Revenue Impact (%)', fontsize=12)
    ax2.set_title('Probability of Revenue Increase (Promotions)', fontweight='bold', fontsize=14)
    ax2.grid(alpha=0.3, axis='y')

    plt.tight_layout()

    if output_path:
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"Promo scenarios plot saved to {output_path}")

    return fig


def plot_revenue_scenarios(results, scenarios=None, output_path: Optional[str] = None, figsize=(12, 8)):
    """
    Plot revenue impact scenarios
    
    Shows:
    - Expected revenue impact
    - Uncertainty bands
    - Probability of positive impact
    
    Parameters:
    ----------
    results : BayesianResults
        Results object
    
    scenarios : list, optional
        Price changes to test (default: -5 to +5)
    
    output_path : str, optional
        Path to save plot
    
    Returns:
    -------
    matplotlib.figure.Figure
    """
    
    if scenarios is None:
        scenarios = [-5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5]
    
    # Calculate impacts (backwards-compatible: uses base price impact)
    impacts = [results.revenue_impact(s) for s in scenarios]
    
    means = [i['revenue_impact_mean'] for i in impacts]
    ci_lower = [i['revenue_impact_ci'][0] for i in impacts]
    ci_upper = [i['revenue_impact_ci'][1] for i in impacts]
    probs = [i['probability_positive'] for i in impacts]
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=figsize)
    
    # Plot 1: Revenue impact
    ax1.plot(scenarios, means, 'o-', color='steelblue', linewidth=2, markersize=8, label='Expected Impact')
    ax1.fill_between(scenarios, ci_lower, ci_upper, alpha=0.3, color='steelblue', label='95% Credible Interval')
    ax1.axhline(0, color='red', linestyle='--', linewidth=1, alpha=0.5)
    ax1.axvline(0, color='gray', linestyle='--', linewidth=1, alpha=0.5)
    
    ax1.set_xlabel('Price Change (%)', fontsize=12)
    ax1.set_ylabel('Revenue Impact (%)', fontsize=12)
    ax1.set_title('Revenue Impact of Price Changes', fontweight='bold', fontsize=14)
    ax1.legend()
    ax1.grid(alpha=0.3)
    
    # Add annotations for key points
    for i, s in enumerate(scenarios):
        if means[i] > 0:
            ax1.annotate(f'{means[i]:+.1f}%', 
                        xy=(s, means[i]), 
                        xytext=(0, 10), 
                        textcoords='offset points',
                        ha='center',
                        fontsize=8,
                        color='green')
    
    # Plot 2: Probability of positive impact
    colors = ['green' if p >= 0.5 else 'red' for p in probs]
    ax2.bar(scenarios, [p * 100 for p in probs], color=colors, alpha=0.7, edgecolor='black')
    ax2.axhline(50, color='black', linestyle='--', linewidth=1, alpha=0.5)
    
    ax2.set_xlabel('Price Change (%)', fontsize=12)
    ax2.set_ylabel('Probability of Positive Revenue Impact (%)', fontsize=12)
    ax2.set_title('Probability of Revenue Increase', fontweight='bold', fontsize=14)
    ax2.grid(alpha=0.3, axis='y')
    
    plt.tight_layout()
    
    if output_path:
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"Revenue scenarios plot saved to {output_path}")
    
    return fig


# ============================================================================
# MODEL COMPARISON (HIERARCHICAL)
# ============================================================================

def plot_group_comparison(results, output_path: Optional[str] = None, figsize=(12, 6)):
    """
    Plot group comparisons for hierarchical models
    
    Shows:
    - Group-specific elasticities
    - Global elasticity
    - Between-group variance
    
    Parameters:
    ----------
    results : HierarchicalResults
        Hierarchical results object
    
    output_path : str, optional
        Path to save plot
    
    Returns:
    -------
    matplotlib.figure.Figure
    """
    
    if not hasattr(results, 'group_elasticities'):
        print("Not a hierarchical model - skipping group comparison")
        return None

    # V2 traces use `base_elasticity` (and optionally `promo_elasticity`) rather than legacy `elasticity_own`.
    posterior = results.trace.posterior
    if 'base_elasticity' in posterior:
        var_group = 'base_elasticity'
        var_global = 'mu_global_base' if 'mu_global_base' in posterior else None
        y_label = 'Base Price Elasticity'
    else:
        var_group = 'elasticity_own'
        var_global = 'mu_global_own' if 'mu_global_own' in posterior else None
        y_label = 'Own-Price Elasticity'
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=figsize)
    
    # Plot 1: Group-specific elasticities
    groups = list(results.group_elasticities.keys())
    means = [results.group_elasticities[g].mean for g in groups]
    ci_lower = [results.group_elasticities[g].ci_lower for g in groups]
    ci_upper = [results.group_elasticities[g].ci_upper for g in groups]
    
    x_pos = np.arange(len(groups))
    
    ax1.bar(x_pos, means, color='steelblue', alpha=0.7, edgecolor='black')
    ax1.errorbar(x_pos, means, 
                yerr=[np.array(means) - np.array(ci_lower),
                      np.array(ci_upper) - np.array(means)],
                fmt='none', color='black', capsize=5)
    
    # Add global mean line
    ax1.axhline(results.global_elasticity.mean, color='red', linestyle='--', 
               linewidth=2, label=f'Global Mean: {results.global_elasticity.mean:.3f}')
    
    ax1.set_xticks(x_pos)
    ax1.set_xticklabels(groups)
    ax1.set_ylabel(y_label)
    ax1.set_title('Retailer-Specific Elasticities', fontweight='bold')
    ax1.legend()
    ax1.grid(alpha=0.3, axis='y')
    
    # Plot 2: Posterior distributions overlay
    for group in groups:
        group_idx = list(results.groups).index(group)
        samples = results.trace.posterior[var_group].values[:, :, group_idx].flatten()
        ax2.hist(samples, bins=30, alpha=0.5, label=group, density=True)
    
    # Add global distribution
    if var_global and var_global in results.trace.posterior:
        global_samples = results.trace.posterior[var_global].values.flatten()
        ax2.hist(global_samples, bins=30, alpha=0.5, label='Global', density=True, color='red')
    
    ax2.set_xlabel(y_label)
    ax2.set_ylabel('Density')
    ax2.set_title('Posterior Distributions by Retailer', fontweight='bold')
    ax2.legend()
    ax2.grid(alpha=0.3)
    
    plt.tight_layout()
    
    if output_path:
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"Group comparison plot saved to {output_path}")
    
    return fig


# ============================================================================
# HTML REPORT GENERATOR
# ============================================================================

def generate_html_report(
    results,
    data,
    output_dir: str = './output',
    report_name: str = 'elasticity_report.html'
):
    """
    Generate complete HTML report with all visualizations
    
    Creates:
    - Executive summary
    - All diagnostic plots
    - Interactive tables
    - Embedded visualizations
    
    Parameters:
    ----------
    results : BayesianResults or HierarchicalResults
        Results object
    
    data : pd.DataFrame
        Original data
    
    output_dir : str
        Output directory
    
    report_name : str
        HTML report filename
    """
    
    # Create output directory
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\nGenerating HTML report in {output_dir}...")
    
    # Generate all plots
    print("  Creating trace plot...")
    trace_path = output_dir / 'trace_plot.png'
    plot_trace(results, output_path=str(trace_path))
    plt.close()
    
    print("  Creating posterior plots...")
    posterior_path = output_dir / 'posterior_plot.png'
    plot_posteriors(results, output_path=str(posterior_path))
    plt.close()
    
    print("  Creating seasonal plot...")
    seasonal_path = output_dir / 'seasonal_plot.png'
    plot_seasonal_patterns(results, data, output_path=str(seasonal_path))
    plt.close()
    
    # V2: base vs promo comparison + separate scenario plots
    base_vs_promo_path = None
    if getattr(results, 'promo_elasticity', None) is not None:
        print("  Creating base vs promo comparison plot...")
        base_vs_promo_path = output_dir / 'base_vs_promo_comparison.png'
        plot_base_vs_promo_comparison(results, output_path=str(base_vs_promo_path))
        plt.close()

    print("  Creating base price revenue scenarios plot...")
    revenue_base_path = output_dir / 'revenue_scenarios_base.png'
    plot_revenue_scenarios_base(results, output_path=str(revenue_base_path))
    plt.close()

    revenue_promo_path = None
    if getattr(results, 'promo_elasticity', None) is not None:
        print("  Creating promotional revenue scenarios plot...")
        revenue_promo_path = output_dir / 'revenue_scenarios_promo.png'
        plot_revenue_scenarios_promo(results, output_path=str(revenue_promo_path))
        plt.close()
    
    # Group comparison (if hierarchical)
    group_path = None
    if hasattr(results, 'group_elasticities'):
        print("  Creating group comparison plot...")
        group_path = output_dir / 'group_comparison.png'
        plot_group_comparison(results, output_path=str(group_path))
        plt.close()
    
    # Generate HTML
    print("  Generating HTML...")
    html_content = _create_html_content(
        results=results,
        data=data,
        output_dir=output_dir,
        group_path=group_path,
        base_vs_promo_path=base_vs_promo_path,
        revenue_base_path=revenue_base_path,
        revenue_promo_path=revenue_promo_path,
    )
    
    # Write HTML file
    report_path = output_dir / report_name
    with open(report_path, 'w') as f:
        f.write(html_content)
    
    print(f"\n✓ HTML report generated: {report_path}")
    print(f"  Open in browser to view complete report")
    
    return str(report_path)


def _create_html_content(results, data, output_dir, group_path, base_vs_promo_path, revenue_base_path, revenue_promo_path):
    """Create HTML content"""
    
    # Determine model type
    is_hierarchical = hasattr(results, 'group_elasticities')
    
    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Price Elasticity Analysis Report</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #333;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 40px;
            border-radius: 10px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        }}
        h1 {{
            color: #667eea;
            border-bottom: 3px solid #667eea;
            padding-bottom: 10px;
            margin-bottom: 30px;
        }}
        h2 {{
            color: #764ba2;
            margin-top: 40px;
            border-left: 5px solid #764ba2;
            padding-left: 15px;
        }}
        .stat-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            margin: 10px 0;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .stat-card h3 {{
            margin: 0 0 10px 0;
            font-size: 14px;
            opacity: 0.9;
        }}
        .stat-card .value {{
            font-size: 28px;
            font-weight: bold;
            margin: 5px 0;
        }}
        .stat-card .subtext {{
            font-size: 12px;
            opacity: 0.8;
        }}
        .convergence {{
            padding: 15px;
            border-radius: 5px;
            margin: 20px 0;
        }}
        .convergence.success {{
            background: #d4edda;
            border: 1px solid #c3e6cb;
            color: #155724;
        }}
        .convergence.warning {{
            background: #fff3cd;
            border: 1px solid #ffeaa7;
            color: #856404;
        }}
        img {{
            max-width: 100%;
            height: auto;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            margin: 20px 0;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background: #667eea;
            color: white;
        }}
        tr:hover {{
            background: #f5f5f5;
        }}
        .footer {{
            margin-top: 50px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            text-align: center;
            color: #666;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🎯 Bayesian Price Elasticity Analysis Report</h1>
        
        <p><strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p><strong>Model Type:</strong> {'Hierarchical (Partial Pooling)' if is_hierarchical else 'Simple'}</p>
        <p><strong>Observations:</strong> {len(data)}</p>
        
        <!-- Convergence Status -->
        <div class="convergence {'success' if results.converged else 'warning'}">
            <h3>{'✓ Model Converged Successfully' if results.converged else '⚠️ Convergence Warnings'}</h3>
            <p>Max R-hat: {results.rhat_max:.4f} (should be < 1.01)</p>
            <p>Min ESS: {results.ess_min:.0f} (should be > 400)</p>
            <p>Divergences: {results.n_divergences} (should be 0)</p>
        </div>
        
        <!-- Key Results -->
        <h2>📊 Key Results</h2>
        
        <div class="stat-card">
            <h3>Base Price Elasticity</h3>
            <div class="value">{results.base_elasticity.mean:.3f}</div>
            <div class="subtext">95% CI: [{results.base_elasticity.ci_lower:.3f}, {results.base_elasticity.ci_upper:.3f}]</div>
            <div class="subtext">{'Demand is ELASTIC (|ε| > 1)' if abs(results.base_elasticity.mean) > 1 else 'Demand is INELASTIC (|ε| < 1)'}</div>
        </div>

        {('<div class=\"stat-card\"><h3>Promotional Elasticity</h3><div class=\"value\">' + f'{results.promo_elasticity.mean:.3f}' + '</div><div class=\"subtext\">95% CI: [' + f'{results.promo_elasticity.ci_lower:.3f}, {results.promo_elasticity.ci_upper:.3f}' + ']</div></div>') if getattr(results, 'promo_elasticity', None) is not None else ''}
        
        {'<div class="stat-card"><h3>Cross-Price Elasticity</h3><div class="value">' + f'{results.elasticity_cross.mean:.3f}' + '</div><div class="subtext">95% CI: [' + f'{results.elasticity_cross.ci_lower:.3f}, {results.elasticity_cross.ci_upper:.3f}' + ']</div></div>' if results.elasticity_cross else ''}
        
        {'<div class="stat-card"><h3>Promotional Effect</h3><div class="value">' + f'{(np.exp(results.beta_promo.mean)-1)*100:+.1f}%' + ' Sales Lift</div><div class="subtext">95% CI: [' + f'{(np.exp(results.beta_promo.ci_lower)-1)*100:.1f}%, {(np.exp(results.beta_promo.ci_upper)-1)*100:.1f}%' + ']</div></div>' if results.beta_promo else ''}
        
        <!-- MCMC Diagnostics -->
        <h2>🔬 MCMC Diagnostics</h2>
        <p>Trace plots show chain mixing and convergence. All chains should mix well with no trends.</p>
        <img src="trace_plot.png" alt="Trace Plot">
        
        <!-- Posterior Distributions -->
        <h2>📈 Posterior Distributions</h2>
        <p>Posterior distributions show parameter estimates with uncertainty. Narrower distributions indicate more certainty.</p>
        <img src="posterior_plot.png" alt="Posterior Distributions">
        
        <!-- Seasonal Analysis -->
        <h2>🌱 Seasonal Analysis</h2>
        <p>Seasonal patterns in sales and estimated seasonal effects relative to Winter baseline.</p>
        <img src="seasonal_plot.png" alt="Seasonal Patterns">
        
        <!-- Base vs Promo Comparison (V2) -->
        {f'<h2>⚖️ Base vs Promotional Elasticity</h2><p>Side-by-side comparison of strategic (base) vs tactical (promo) responsiveness.</p><img src=\"base_vs_promo_comparison.png\" alt=\"Base vs Promo Comparison\">' if base_vs_promo_path else ''}

        <!-- Revenue Scenarios - Base -->
        <h2>💰 Revenue Scenarios - Base Price Changes</h2>
        <p>Expected revenue impact of different <strong>base price</strong> changes with uncertainty bands.</p>
        <img src="revenue_scenarios_base.png" alt="Revenue Scenarios (Base)">

        <!-- Revenue Scenarios - Promo -->
        {f'<h2>🏷️ Revenue Scenarios - Promotions</h2><p>Expected revenue impact of promotional discount depths with uncertainty bands.</p><img src=\"revenue_scenarios_promo.png\" alt=\"Revenue Scenarios (Promo)\">' if revenue_promo_path else ''}
        
        <!-- Group Comparison (if hierarchical) -->
        {f'<h2>🏪 Retailer Comparison</h2><p>Group-specific elasticities with partial pooling toward global mean.</p><img src="group_comparison.png" alt="Group Comparison">' if group_path else ''}
        
        <!-- Revenue Impact Table (Base Price) -->
        <h2>📋 Revenue Impact Table (Base Price)</h2>
        <table>
            <thead>
                <tr>
                    <th>Base Price Change</th>
                    <th>Expected Volume Impact</th>
                    <th>Expected Revenue Impact</th>
                    <th>Probability Positive</th>
                </tr>
            </thead>
            <tbody>
"""
    
    # Add base price scenarios to table
    for price_change in [-5, -3, -1, 1, 3, 5]:
        impact = results.revenue_impact(price_change)
        html += f"""
                <tr>
                    <td>{price_change:+d}%</td>
                    <td>{impact['volume_impact_mean']:+.1f}%</td>
                    <td style="color: {'green' if impact['revenue_impact_mean'] > 0 else 'red'}; font-weight: bold;">
                        {impact['revenue_impact_mean']:+.1f}%
                    </td>
                    <td>{impact['probability_positive']*100:.0f}%</td>
                </tr>
"""

    # Optional: promotions table (if promo elasticity is available)
    if revenue_promo_path:
        html += """
            </tbody>
        </table>

        <h2>📋 Revenue Impact Table (Promotions)</h2>
        <table>
            <thead>
                <tr>
                    <th>Discount Depth</th>
                    <th>Expected Volume Impact</th>
                    <th>Expected Revenue Impact</th>
                    <th>Probability Positive</th>
                </tr>
            </thead>
            <tbody>
"""

        for discount in [5, 10, 15, 20]:
            impact = results.promo_impact(discount)
            html += f"""
                <tr>
                    <td>{discount:.0f}% off</td>
                    <td>{impact['volume_impact_mean']:+.1f}%</td>
                    <td style="color: {'green' if impact['revenue_impact_mean'] > 0 else 'red'}; font-weight: bold;">
                        {impact['revenue_impact_mean']:+.1f}%
                    </td>
                    <td>{impact['probability_positive']*100:.0f}%</td>
                </tr>
"""
    
    html += """
            </tbody>
        </table>
        
        <div class="footer">
            <p>Generated by Bayesian Price Elasticity Analysis System</p>
            <p>© 2026 | Production-Ready Analytics</p>
        </div>
    </div>
</body>
</html>
"""
    
    return html


# ============================================================================
# CONVENIENCE FUNCTION
# ============================================================================

def create_all_plots(results, data, output_dir='./plots'):
    """
    Create all plots at once
    
    Parameters:
    ----------
    results : BayesianResults
        Results object
    
    data : pd.DataFrame
        Original data
    
    output_dir : str
        Output directory
    
    Returns:
    -------
    Dict
        Dictionary of figure objects
    """
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    plots = {}
    
    plots['trace'] = plot_trace(results, output_path=str(output_dir / 'trace.png'))
    plt.close()
    
    plots['posteriors'] = plot_posteriors(results, output_path=str(output_dir / 'posteriors.png'))
    plt.close()
    
    plots['seasonal'] = plot_seasonal_patterns(results, data, output_path=str(output_dir / 'seasonal.png'))
    plt.close()

    # V2: separate scenario plots
    plots['revenue_base'] = plot_revenue_scenarios_base(results, output_path=str(output_dir / 'revenue_base.png'))
    plt.close()

    if getattr(results, 'promo_elasticity', None) is not None:
        plots['revenue_promo'] = plot_revenue_scenarios_promo(results, output_path=str(output_dir / 'revenue_promo.png'))
        plt.close()

        plots['base_vs_promo'] = plot_base_vs_promo_comparison(results, output_path=str(output_dir / 'base_vs_promo.png'))
        plt.close()
    else:
        # Legacy combined plot (kept for convenience)
        plots['revenue'] = plot_revenue_scenarios(results, output_path=str(output_dir / 'revenue.png'))
        plt.close()
    
    if hasattr(results, 'group_elasticities'):
        plots['groups'] = plot_group_comparison(results, output_path=str(output_dir / 'groups.png'))
        plt.close()
    
    print(f"\n✓ All plots saved to {output_dir}")
    
    return plots
