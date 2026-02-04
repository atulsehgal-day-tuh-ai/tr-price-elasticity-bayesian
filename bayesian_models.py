"""
Bayesian Price Elasticity Models

Complete Bayesian modeling system with PyMC for price elasticity analysis.

Features:
- Simple (non-hierarchical) Bayesian model
- Hierarchical model with partial pooling
- Three prior specifications (default, informative, vague)
- Full MCMC sampling with convergence diagnostics
- Comprehensive results with uncertainty quantification
- Revenue scenario calculations
- Probability statements

Usage:
    from bayesian_models import HierarchicalBayesianModel
    
    model = HierarchicalBayesianModel()
    results = model.fit(df)
    print(results.summary())
"""

import numpy as np
import pandas as pd
import pymc as pm
import arviz as az
from typing import Dict, Optional, List, Callable
from dataclasses import dataclass
import logging
import warnings

warnings.filterwarnings('ignore', category=FutureWarning)


# ============================================================================
# PRIOR LIBRARY
# ============================================================================

class PriorLibrary:
    """
    Pre-defined prior specifications for elasticity models
    
    Three sets:
    1. default - Weakly informative (RECOMMENDED)
    2. informative - Based on your frequentist results
    3. vague - Non-informative
    """
    
    @staticmethod
    def get_priors(prior_type: str = 'default') -> Dict:
        """
        Get prior specifications
        
        Parameters:
        ----------
        prior_type : str
            'default', 'informative', or 'vague'
        
        Returns:
        -------
        Dict
            Prior specifications for all parameters
        """
        
        if prior_type == 'default':
            return PriorLibrary._default_priors()
        elif prior_type == 'informative':
            return PriorLibrary._informative_priors()
        elif prior_type == 'vague':
            return PriorLibrary._vague_priors()
        else:
            raise ValueError(f"Unknown prior_type: {prior_type}")
    
    @staticmethod
    def _default_priors() -> Dict:
        """Weakly informative priors (RECOMMENDED)"""
        return {
            # V2: base vs promo elasticities
            'base_elasticity': {'mu': -2.0, 'sigma': 0.5},
            'promo_elasticity': {'mu': -4.0, 'sigma': 1.0},
            # Backwards-compat (V1 naming)
            'elasticity_own': {'mu': -2.0, 'sigma': 0.5},
            'elasticity_cross': {'mu': 0.15, 'sigma': 0.15},
            'beta_promo': {'mu': 0.2, 'sigma': 0.2},
            'beta_spring': {'mu': 0.0, 'sigma': 0.2},
            'beta_summer': {'mu': 0.0, 'sigma': 0.2},
            'beta_fall': {'mu': 0.0, 'sigma': 0.2},
            'beta_time': {'mu': 0.0, 'sigma': 0.01},
            'intercept': {'mu': 10.0, 'sigma': 2.0},
            'sigma': {'sigma': 0.5},
            'sigma_group': {'sigma': 0.3}
        }
    
    @staticmethod
    def _informative_priors() -> Dict:
        """Informative priors based on frequentist results"""
        return {
            'base_elasticity': {'mu': -1.8, 'sigma': 0.3},
            'promo_elasticity': {'mu': -3.5, 'sigma': 0.5},
            # Backwards-compat (V1 naming)
            'elasticity_own': {'mu': -2.22, 'sigma': 0.3},
            'elasticity_cross': {'mu': 0.07, 'sigma': 0.1},
            'beta_promo': {'mu': 0.25, 'sigma': 0.15},
            'beta_spring': {'mu': 0.12, 'sigma': 0.05},
            'beta_summer': {'mu': 0.0, 'sigma': 0.1},
            'beta_fall': {'mu': 0.07, 'sigma': 0.05},
            'beta_time': {'mu': -0.001, 'sigma': 0.005},
            'intercept': {'mu': 17.5, 'sigma': 1.0},
            'sigma': {'sigma': 0.3},
            'sigma_group': {'sigma': 0.2}
        }
    
    @staticmethod
    def _vague_priors() -> Dict:
        """Vague (non-informative) priors"""
        return {
            'base_elasticity': {'mu': 0.0, 'sigma': 5.0},
            'promo_elasticity': {'mu': 0.0, 'sigma': 5.0},
            # Backwards-compat (V1 naming)
            'elasticity_own': {'mu': 0.0, 'sigma': 5.0},
            'elasticity_cross': {'mu': 0.0, 'sigma': 2.0},
            'beta_promo': {'mu': 0.0, 'sigma': 1.0},
            'beta_spring': {'mu': 0.0, 'sigma': 1.0},
            'beta_summer': {'mu': 0.0, 'sigma': 1.0},
            'beta_fall': {'mu': 0.0, 'sigma': 1.0},
            'beta_time': {'mu': 0.0, 'sigma': 0.1},
            'intercept': {'mu': 0.0, 'sigma': 10.0},
            'sigma': {'sigma': 2.0},
            'sigma_group': {'sigma': 1.0}
        }


# ============================================================================
# RESULTS CLASSES
# ============================================================================

@dataclass
class PosteriorSummary:
    """Summary statistics for a posterior distribution"""
    
    mean: float
    median: float
    std: float
    ci_lower: float
    ci_upper: float
    
    def __str__(self):
        return f"{self.mean:.3f} [{self.ci_lower:.3f}, {self.ci_upper:.3f}]"


class BayesianResults:
    """
    Results container for Bayesian elasticity models
    
    Provides easy access to:
    - Posterior estimates
    - Uncertainty quantification
    - Probability statements
    - Revenue scenarios
    """
    
    def __init__(self, trace, model, data, config, priors):
        """Initialize results"""
        self.trace = trace
        self.model = model
        self.data = data
        self.config = config
        self.priors = priors
        
        # Extract posteriors
        self._extract_posteriors()
        
        # Check convergence
        self._check_convergence()
    
    def _extract_posteriors(self):
        """Extract posterior summaries"""

        # V2: Base price elasticity (preferred). Fall back to V1 `elasticity_own` if needed.
        if 'base_elasticity' in self.trace.posterior:
            base_samples = self.trace.posterior['base_elasticity'].values.flatten()
        else:
            base_samples = self.trace.posterior['elasticity_own'].values.flatten()

        self.base_elasticity = PosteriorSummary(
            mean=base_samples.mean(),
            median=np.median(base_samples),
            std=base_samples.std(),
            ci_lower=np.percentile(base_samples, 2.5),
            ci_upper=np.percentile(base_samples, 97.5),
        )
        self.base_elasticity_samples = base_samples

        # V2: Promotional elasticity (coefficient on promo-depth / price-change during promos)
        # May be absent in legacy traces.
        if 'promo_elasticity' in self.trace.posterior:
            promo_samples = self.trace.posterior['promo_elasticity'].values.flatten()
            self.promo_elasticity = PosteriorSummary(
                mean=promo_samples.mean(),
                median=np.median(promo_samples),
                std=promo_samples.std(),
                ci_lower=np.percentile(promo_samples, 2.5),
                ci_upper=np.percentile(promo_samples, 97.5),
            )
            self.promo_elasticity_samples = promo_samples
        else:
            self.promo_elasticity = None
            self.promo_elasticity_samples = None

        # Backwards-compat aliases
        self.elasticity_own = self.base_elasticity
        self.elasticity_own_samples = self.base_elasticity_samples
        
        # Cross-price elasticity
        if 'elasticity_cross' in self.trace.posterior:
            samples = self.trace.posterior['elasticity_cross'].values.flatten()
            self.elasticity_cross = PosteriorSummary(
                mean=samples.mean(),
                median=np.median(samples),
                std=samples.std(),
                ci_lower=np.percentile(samples, 2.5),
                ci_upper=np.percentile(samples, 97.5)
            )
        else:
            self.elasticity_cross = None
        
        # Legacy: Promo effect (V1)
        if 'beta_promo' in self.trace.posterior:
            samples = self.trace.posterior['beta_promo'].values.flatten()
            self.beta_promo = PosteriorSummary(
                mean=samples.mean(),
                median=np.median(samples),
                std=samples.std(),
                ci_lower=np.percentile(samples, 2.5),
                ci_upper=np.percentile(samples, 97.5)
            )
        else:
            self.beta_promo = None
        
        # Seasonal effects
        self.seasonal_effects = {}
        for season in ['spring', 'summer', 'fall']:
            param = f'beta_{season}'
            if param in self.trace.posterior:
                samples = self.trace.posterior[param].values.flatten()
                self.seasonal_effects[season.capitalize()] = PosteriorSummary(
                    mean=samples.mean(),
                    median=np.median(samples),
                    std=samples.std(),
                    ci_lower=np.percentile(samples, 2.5),
                    ci_upper=np.percentile(samples, 97.5)
                )
    
    def _check_convergence(self):
        """Check MCMC convergence"""
        
        # R-hat
        rhat = az.rhat(self.trace)
        self.rhat_max = float(rhat.max())
        
        # ESS
        ess = az.ess(self.trace)
        self.ess_min = float(ess.min())
        
        # Divergences
        divergences = self.trace.sample_stats.diverging.sum().values
        self.n_divergences = int(divergences)
        
        # Overall convergence
        self.converged = (self.rhat_max < 1.01 and self.ess_min > 400 and self.n_divergences == 0)
    
    def summary(self) -> str:
        """Print summary"""
        
        lines = []
        lines.append("="*80)
        lines.append("BAYESIAN ELASTICITY MODEL RESULTS")
        lines.append("="*80)
        
        # Convergence
        if self.converged:
            lines.append("\n✓ Model converged successfully")
        else:
            lines.append("\n⚠️  Convergence warnings:")
            if self.rhat_max >= 1.01:
                lines.append(f"  - Max R-hat: {self.rhat_max:.4f} (should be < 1.01)")
            if self.ess_min <= 400:
                lines.append(f"  - Min ESS: {self.ess_min:.0f} (should be > 400)")
            if self.n_divergences > 0:
                lines.append(f"  - Divergences: {self.n_divergences} (should be 0)")
        
        # Sample info
        lines.append(f"\nObservations: {len(self.data)}")
        lines.append(f"Chains: {self.trace.posterior.dims['chain']}")
        lines.append(f"Samples per chain: {self.trace.posterior.dims['draw']}")
        
        # Main results
        lines.append("\n" + "-"*80)
        lines.append("POSTERIOR ESTIMATES")
        lines.append("-"*80)
        
        lines.append(f"\nBase Price Elasticity: {self.base_elasticity}")
        if abs(self.base_elasticity.mean) > 1:
            lines.append(f"  → Demand is ELASTIC (price increases hurt revenue)")
        else:
            lines.append(f"  → Demand is INELASTIC (price increases boost revenue)")

        if self.promo_elasticity is not None:
            lines.append(f"\nPromotional Elasticity: {self.promo_elasticity}")
            try:
                multiplier = abs(self.promo_elasticity.mean) / max(abs(self.base_elasticity.mean), 1e-9)
                lines.append(f"  → Promotions are ~{multiplier:.1f}x more responsive than base price (magnitude ratio)")
            except Exception:
                pass
        
        if self.elasticity_cross:
            lines.append(f"\nCross-Price Elasticity: {self.elasticity_cross}")
        
        if self.beta_promo and self.promo_elasticity is None:
            # Only show this legacy interpretation if we did not estimate promo elasticity.
            lines.append(f"\nPromotional Effect: {self.beta_promo}")
            lift = (np.exp(self.beta_promo.mean) - 1) * 100
            lines.append(f"  → Promotions boost sales by {lift:.1f}%")
        
        if self.seasonal_effects:
            lines.append(f"\nSeasonal Effects:")
            for season, summary in self.seasonal_effects.items():
                lines.append(f"  {season}: {summary}")
                lift = (np.exp(summary.mean) - 1) * 100
                lines.append(f"    → {lift:+.1f}% vs Winter")
        
        lines.append("\n" + "="*80)
        
        return "\n".join(lines)
    
    def probability(self, statement: str) -> float:
        """
        Calculate probability of a statement
        
        Example:
        -------
        >>> prob = results.probability('elasticity_own < -2.0')
        >>> print(f"P(elasticity < -2.0) = {prob:.1%}")
        """
        
        if '<' in statement:
            var, threshold = statement.split('<')
            var = var.strip()
            threshold = float(threshold.strip())
            samples = self.trace.posterior[var].values.flatten()
            return (samples < threshold).mean()
        
        elif '>' in statement:
            var, threshold = statement.split('>')
            var = var.strip()
            threshold = float(threshold.strip())
            samples = self.trace.posterior[var].values.flatten()
            return (samples > threshold).mean()
        
        else:
            raise ValueError("Statement must contain '<' or '>'")
    
    def compare_elasticities(self) -> Dict:
        """
        Compare promotional elasticity magnitude vs base elasticity magnitude.

        Returns:
        -------
        Dict with multiplier distribution (|promo| / |base|) and probability promo is larger in magnitude.
        """
        if self.promo_elasticity_samples is None:
            raise ValueError("Promotional elasticity not available in this result.")

        base = self.base_elasticity_samples
        promo = self.promo_elasticity_samples

        ratio = (np.abs(promo) / np.maximum(np.abs(base), 1e-9))
        return {
            'multiplier_mean': float(ratio.mean()),
            'multiplier_ci': [float(np.percentile(ratio, 2.5)), float(np.percentile(ratio, 97.5))],
            'probability_promo_more_responsive': float((np.abs(promo) > np.abs(base)).mean()),
        }

    def base_price_impact(self, price_change_pct: float) -> Dict:
        """
        Revenue impact of a permanent/base price change using base price elasticity.

        Uses multiplicative revenue math:
          revenue_multiplier = (1 + volume_change%) * (1 + price_change%)
        """
        base_samples = self.base_elasticity_samples
        volume_impact = base_samples * price_change_pct  # % volume change

        revenue_multiplier = (1 + volume_impact / 100.0) * (1 + price_change_pct / 100.0)
        revenue_impact = (revenue_multiplier - 1) * 100.0

        return {
            'price_change_pct': float(price_change_pct),
            'volume_impact_mean': float(volume_impact.mean()),
            'volume_impact_ci': [float(np.percentile(volume_impact, 2.5)), float(np.percentile(volume_impact, 97.5))],
            'revenue_impact_mean': float(revenue_impact.mean()),
            'revenue_impact_ci': [float(np.percentile(revenue_impact, 2.5)), float(np.percentile(revenue_impact, 97.5))],
            'probability_positive': float((revenue_impact > 0).mean()),
        }

    def promo_impact(self, discount_depth_pct: float) -> Dict:
        """
        Revenue impact of a promotional discount of given depth (percent off),
        using promotional elasticity.

        Parameters:
        ----------
        discount_depth_pct : float
            Positive discount depth, e.g. 10 means 10% off.
        """
        if self.promo_elasticity_samples is None:
            raise ValueError("Promotional elasticity not available in this result.")

        price_change_pct = -abs(float(discount_depth_pct))
        promo_samples = self.promo_elasticity_samples

        volume_impact = promo_samples * price_change_pct  # % volume change (negative * negative => positive)

        revenue_multiplier = (1 + volume_impact / 100.0) * (1 + price_change_pct / 100.0)
        revenue_impact = (revenue_multiplier - 1) * 100.0

        return {
            'discount_depth_pct': float(discount_depth_pct),
            'price_change_pct': float(price_change_pct),
            'volume_impact_mean': float(volume_impact.mean()),
            'volume_impact_ci': [float(np.percentile(volume_impact, 2.5)), float(np.percentile(volume_impact, 97.5))],
            'revenue_impact_mean': float(revenue_impact.mean()),
            'revenue_impact_ci': [float(np.percentile(revenue_impact, 2.5)), float(np.percentile(revenue_impact, 97.5))],
            'probability_positive': float((revenue_impact > 0).mean()),
        }

    def revenue_impact(self, price_change_pct: float) -> Dict:
        """
        Backwards-compatible alias: treat this as base price impact.
        """
        return self.base_price_impact(price_change_pct=price_change_pct)


class HierarchicalResults(BayesianResults):
    """Results for hierarchical models with group-specific estimates"""
    
    def __init__(self, trace, model, data, config, priors, groups):
        """Initialize hierarchical results"""
        self.groups = groups
        super().__init__(trace, model, data, config, priors)
        
        # Extract group-specific results
        self._extract_group_posteriors()
    
    def _extract_group_posteriors(self):
        """Extract group-specific posteriors"""
        is_v2 = 'mu_global_base' in self.trace.posterior and 'base_elasticity' in self.trace.posterior

        if is_v2:
            # Global base elasticity
            samples = self.trace.posterior['mu_global_base'].values.flatten()
            self.global_base_elasticity = PosteriorSummary(
                mean=samples.mean(),
                median=np.median(samples),
                std=samples.std(),
                ci_lower=np.percentile(samples, 2.5),
                ci_upper=np.percentile(samples, 97.5),
            )

            # Global promo elasticity
            samples = self.trace.posterior['mu_global_promo'].values.flatten()
            self.global_promo_elasticity = PosteriorSummary(
                mean=samples.mean(),
                median=np.median(samples),
                std=samples.std(),
                ci_lower=np.percentile(samples, 2.5),
                ci_upper=np.percentile(samples, 97.5),
            )

            # Between-group variance (base)
            samples = self.trace.posterior['sigma_group_base'].values.flatten()
            self.sigma_group_base = PosteriorSummary(
                mean=samples.mean(),
                median=np.median(samples),
                std=samples.std(),
                ci_lower=np.percentile(samples, 2.5),
                ci_upper=np.percentile(samples, 97.5),
            )

            # Between-group variance (promo)
            samples = self.trace.posterior['sigma_group_promo'].values.flatten()
            self.sigma_group_promo = PosteriorSummary(
                mean=samples.mean(),
                median=np.median(samples),
                std=samples.std(),
                ci_lower=np.percentile(samples, 2.5),
                ci_upper=np.percentile(samples, 97.5),
            )

            # Group-specific elasticities
            self.group_base_elasticities = {}
            self.group_promo_elasticities = {}

            base_samples_3d = self.trace.posterior['base_elasticity'].values
            promo_samples_3d = self.trace.posterior['promo_elasticity'].values

            for i, group in enumerate(self.groups):
                s_base = base_samples_3d[:, :, i].flatten()
                s_promo = promo_samples_3d[:, :, i].flatten()
                self.group_base_elasticities[group] = PosteriorSummary(
                    mean=s_base.mean(),
                    median=np.median(s_base),
                    std=s_base.std(),
                    ci_lower=np.percentile(s_base, 2.5),
                    ci_upper=np.percentile(s_base, 97.5),
                )
                self.group_promo_elasticities[group] = PosteriorSummary(
                    mean=s_promo.mean(),
                    median=np.median(s_promo),
                    std=s_promo.std(),
                    ci_lower=np.percentile(s_promo, 2.5),
                    ci_upper=np.percentile(s_promo, 97.5),
                )

            # Backwards-compat aliases
            self.global_elasticity = self.global_base_elasticity
            self.sigma_group = self.sigma_group_base
            self.group_elasticities = self.group_base_elasticities

        else:
            # Legacy V1 hierarchical extraction
            samples = self.trace.posterior['mu_global_own'].values.flatten()
            self.global_elasticity = PosteriorSummary(
                mean=samples.mean(),
                median=np.median(samples),
                std=samples.std(),
                ci_lower=np.percentile(samples, 2.5),
                ci_upper=np.percentile(samples, 97.5),
            )

            samples = self.trace.posterior['sigma_group_own'].values.flatten()
            self.sigma_group = PosteriorSummary(
                mean=samples.mean(),
                median=np.median(samples),
                std=samples.std(),
                ci_lower=np.percentile(samples, 2.5),
                ci_upper=np.percentile(samples, 97.5),
            )

            self.group_elasticities = {}
            elasticity_samples = self.trace.posterior['elasticity_own'].values
            for i, group in enumerate(self.groups):
                s = elasticity_samples[:, :, i].flatten()
                self.group_elasticities[group] = PosteriorSummary(
                    mean=s.mean(),
                    median=np.median(s),
                    std=s.std(),
                    ci_lower=np.percentile(s, 2.5),
                    ci_upper=np.percentile(s, 97.5),
                )
    
    def compare_groups(self, group1: str, group2: str, elasticity_type: str = 'base') -> Dict:
        """
        Compare two groups statistically
        
        Returns:
        -------
        Dict
            Comparison statistics
        """
        
        idx1 = list(self.groups).index(group1)
        idx2 = list(self.groups).index(group2)
        
        if 'base_elasticity' in self.trace.posterior and elasticity_type.lower() in ['base', 'promo']:
            var = 'base_elasticity' if elasticity_type.lower() == 'base' else 'promo_elasticity'
        else:
            var = 'elasticity_own'

        samples1 = self.trace.posterior[var].values[:, :, idx1].flatten()
        samples2 = self.trace.posterior[var].values[:, :, idx2].flatten()
        
        diff = samples1 - samples2
        
        return {
            'difference_mean': diff.mean(),
            'difference_ci': [np.percentile(diff, 2.5), np.percentile(diff, 97.5)],
            'probability': (diff < 0).mean()  # P(group1 more elastic than group2)
        }


# ============================================================================
# SIMPLE BAYESIAN MODEL
# ============================================================================

class SimpleBayesianModel:
    """
    Simple (non-hierarchical) Bayesian elasticity model
    
    Use for:
    - Overall data (BJ's + Sam's combined)
    - Single retailer analysis
    
    Example:
    -------
    >>> model = SimpleBayesianModel(priors='default')
    >>> results = model.fit(df)
    """
    
    def __init__(
        self,
        priors: str = 'default',
        n_samples: int = 2000,
        n_tune: int = 1000,
        n_chains: int = 4,
        target_accept: float = 0.95,
        random_seed: int = 42,
        verbose: bool = True
    ):
        """Initialize model"""
        self.priors = PriorLibrary.get_priors(priors)
        self.n_samples = n_samples
        self.n_tune = n_tune
        self.n_chains = n_chains
        self.target_accept = target_accept
        self.random_seed = random_seed
        self.verbose = verbose
        
        self.logger = self._setup_logger()
        self.model = None
        self.trace = None
    
    def _setup_logger(self):
        """Setup logging"""
        logger = logging.getLogger('SimpleBayesianModel')
        logger.setLevel(logging.INFO if self.verbose else logging.WARNING)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    def fit(self, data: pd.DataFrame) -> BayesianResults:
        """
        Fit Bayesian model
        
        Parameters:
        ----------
        data : pd.DataFrame
            Model-ready data from data_prep.py
        
        Returns:
        -------
        BayesianResults
            Results object
        """
        
        self.logger.info("="*80)
        self.logger.info("FITTING SIMPLE BAYESIAN MODEL")
        self.logger.info("="*80)
        
        # Build model
        self.logger.info("\nBuilding model...")
        self._build_model(data)
        
        # Sample
        self.logger.info(f"\nSampling ({self.n_chains} chains × {self.n_samples} samples)...")
        self._sample()
        
        # Create results
        self.logger.info("\nProcessing results...")
        results = BayesianResults(
            trace=self.trace,
            model=self.model,
            data=data,
            config=self.__dict__,
            priors=self.priors
        )
        
        self.logger.info("\n" + "="*80)
        self.logger.info("✓ FITTING COMPLETE")
        self.logger.info("="*80)
        
        return results
    
    def _build_model(self, data: pd.DataFrame):
        """Build PyMC model"""
        
        # Extract data
        y = data['Log_Unit_Sales_SI'].values
        use_dual = ('Log_Base_Price_SI' in data.columns) and ('Promo_Depth_SI' in data.columns)
        X_base = data['Log_Base_Price_SI'].values if use_dual else data['Log_Price_SI'].values
        X_cross = data['Log_Price_PL'].values
        X_has_competitor = data['has_competitor'].values if 'has_competitor' in data else np.ones(len(data))

        if use_dual:
            X_promo = data['Promo_Depth_SI'].values
            X_has_promo = data['has_promo'].values if 'has_promo' in data else np.ones(len(data))
        else:
            X_promo = data['Promo_Intensity_SI'].values if 'Promo_Intensity_SI' in data else None
            X_has_promo = data['has_promo'].values if 'has_promo' in data else (np.ones(len(data)) if X_promo is not None else None)

        # Safety: ensure no NaNs propagate into the linear predictor
        X_cross = np.nan_to_num(X_cross, nan=0.0)
        X_has_competitor = np.nan_to_num(X_has_competitor, nan=0.0)
        if X_promo is not None:
            X_promo = np.nan_to_num(X_promo, nan=0.0)
            X_has_promo = np.nan_to_num(X_has_promo, nan=0.0)
        X_spring = data['Spring'].values if 'Spring' in data else None
        X_summer = data['Summer'].values if 'Summer' in data else None
        X_fall = data['Fall'].values if 'Fall' in data else None
        X_time = data['Week_Number'].values if 'Week_Number' in data else None
        
        with pm.Model() as model:
            # Priors
            intercept = pm.Normal('intercept', 
                                 mu=self.priors['intercept']['mu'],
                                 sigma=self.priors['intercept']['sigma'])

            base_elasticity = pm.Normal(
                'base_elasticity',
                mu=self.priors['base_elasticity']['mu'],
                sigma=self.priors['base_elasticity']['sigma']
            )
            
            elasticity_cross = pm.Normal('elasticity_cross',
                                         mu=self.priors['elasticity_cross']['mu'],
                                         sigma=self.priors['elasticity_cross']['sigma'])
            
            # Linear predictor
            mu = intercept + base_elasticity * X_base + elasticity_cross * (X_cross * X_has_competitor)
            
            # Optional features
            if X_promo is not None:
                if use_dual:
                    promo_elasticity = pm.Normal(
                        'promo_elasticity',
                        mu=self.priors['promo_elasticity']['mu'],
                        sigma=self.priors['promo_elasticity']['sigma']
                    )
                    mu += promo_elasticity * (X_promo * X_has_promo)
                else:
                    beta_promo = pm.Normal('beta_promo',
                                          mu=self.priors['beta_promo']['mu'],
                                          sigma=self.priors['beta_promo']['sigma'])
                    mu += beta_promo * (X_promo * X_has_promo)
            
            if X_spring is not None:
                beta_spring = pm.Normal('beta_spring',
                                       mu=self.priors['beta_spring']['mu'],
                                       sigma=self.priors['beta_spring']['sigma'])
                beta_summer = pm.Normal('beta_summer',
                                       mu=self.priors['beta_summer']['mu'],
                                       sigma=self.priors['beta_summer']['sigma'])
                beta_fall = pm.Normal('beta_fall',
                                     mu=self.priors['beta_fall']['mu'],
                                     sigma=self.priors['beta_fall']['sigma'])
                mu += beta_spring * X_spring + beta_summer * X_summer + beta_fall * X_fall
            
            if X_time is not None:
                beta_time = pm.Normal('beta_time',
                                     mu=self.priors['beta_time']['mu'],
                                     sigma=self.priors['beta_time']['sigma'])
                mu += beta_time * X_time
            
            # Likelihood
            sigma = pm.HalfNormal('sigma', sigma=self.priors['sigma']['sigma'])
            y_obs = pm.Normal('y_obs', mu=mu, sigma=sigma, observed=y)
        
        self.model = model
    
    def _sample(self):
        """Run MCMC sampling"""
        
        with self.model:
            self.trace = pm.sample(
                draws=self.n_samples,
                tune=self.n_tune,
                chains=self.n_chains,
                target_accept=self.target_accept,
                random_seed=self.random_seed,
                return_inferencedata=True,
                progressbar=self.verbose
            )


# ============================================================================
# HIERARCHICAL BAYESIAN MODEL
# ============================================================================

class HierarchicalBayesianModel:
    """
    Hierarchical Bayesian model with partial pooling
    
    Use for:
    - Multiple retailers (BJ's, Sam's, Costco)
    - Want to borrow strength across groups
    - More stable group-specific estimates
    
    Example:
    -------
    >>> model = HierarchicalBayesianModel()
    >>> results = model.fit(df)  # df must have 'Retailer' column
    """
    
    def __init__(
        self,
        priors: str = 'default',
        n_samples: int = 2000,
        n_tune: int = 1000,
        n_chains: int = 4,
        target_accept: float = 0.95,
        random_seed: int = 42,
        verbose: bool = True
    ):
        """Initialize model"""
        self.priors = PriorLibrary.get_priors(priors)
        self.n_samples = n_samples
        self.n_tune = n_tune
        self.n_chains = n_chains
        self.target_accept = target_accept
        self.random_seed = random_seed
        self.verbose = verbose
        
        self.logger = self._setup_logger()
        self.model = None
        self.trace = None
        self.groups = None
    
    def _setup_logger(self):
        """Setup logging"""
        logger = logging.getLogger('HierarchicalBayesianModel')
        logger.setLevel(logging.INFO if self.verbose else logging.WARNING)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    def fit(self, data: pd.DataFrame) -> HierarchicalResults:
        """
        Fit hierarchical Bayesian model
        
        Parameters:
        ----------
        data : pd.DataFrame
            Must have 'Retailer' column
        
        Returns:
        -------
        HierarchicalResults
            Results object with group-specific estimates
        """
        
        if 'Retailer' not in data.columns:
            raise ValueError("Hierarchical model requires 'Retailer' column")
        
        self.logger.info("="*80)
        self.logger.info("FITTING HIERARCHICAL BAYESIAN MODEL")
        self.logger.info("="*80)
        
        # Get groups
        self.groups = data['Retailer'].unique()
        self.logger.info(f"\nGroups: {list(self.groups)}")
        
        # Build model
        self.logger.info("\nBuilding hierarchical model...")
        self._build_model(data)
        
        # Sample
        self.logger.info(f"\nSampling ({self.n_chains} chains × {self.n_samples} samples)...")
        self._sample()
        
        # Create results
        self.logger.info("\nProcessing results...")
        results = HierarchicalResults(
            trace=self.trace,
            model=self.model,
            data=data,
            config=self.__dict__,
            priors=self.priors,
            groups=self.groups
        )
        
        self.logger.info("\n" + "="*80)
        self.logger.info("✓ FITTING COMPLETE")
        self.logger.info("="*80)
        
        return results
    
    def _build_model(self, data: pd.DataFrame):
        """Build hierarchical PyMC model"""
        
        # Extract data
        y = data['Log_Unit_Sales_SI'].values
        use_dual = ('Log_Base_Price_SI' in data.columns) and ('Promo_Depth_SI' in data.columns)
        X_base = data['Log_Base_Price_SI'].values if use_dual else data['Log_Price_SI'].values
        X_cross = data['Log_Price_PL'].values
        X_has_competitor = data['has_competitor'].values if 'has_competitor' in data else np.ones(len(data))
        group_idx = pd.Categorical(data['Retailer']).codes
        n_groups = len(self.groups)
        
        if use_dual:
            X_promo = data['Promo_Depth_SI'].values
            X_has_promo = data['has_promo'].values if 'has_promo' in data else np.ones(len(data))
        else:
            X_promo = data['Promo_Intensity_SI'].values if 'Promo_Intensity_SI' in data else None
            X_has_promo = data['has_promo'].values if 'has_promo' in data else (np.ones(len(data)) if X_promo is not None else None)
        X_spring = data['Spring'].values if 'Spring' in data else None
        X_summer = data['Summer'].values if 'Summer' in data else None
        X_fall = data['Fall'].values if 'Fall' in data else None

        # Safety: ensure no NaNs propagate into the linear predictor
        X_cross = np.nan_to_num(X_cross, nan=0.0)
        X_has_competitor = np.nan_to_num(X_has_competitor, nan=0.0)
        if X_promo is not None:
            X_promo = np.nan_to_num(X_promo, nan=0.0)
            X_has_promo = np.nan_to_num(X_has_promo, nan=0.0)
        
        with pm.Model() as model:
            if use_dual:
                # GLOBAL (POPULATION) PARAMETERS
                mu_global_base = pm.Normal(
                    'mu_global_base',
                    mu=self.priors['base_elasticity']['mu'],
                    sigma=self.priors['base_elasticity']['sigma'],
                )
                sigma_group_base = pm.HalfNormal(
                    'sigma_group_base',
                    sigma=self.priors['sigma_group']['sigma'],
                )

                mu_global_promo = pm.Normal(
                    'mu_global_promo',
                    mu=self.priors['promo_elasticity']['mu'],
                    sigma=self.priors['promo_elasticity']['sigma'],
                )
                sigma_group_promo = pm.HalfNormal(
                    'sigma_group_promo',
                    sigma=self.priors['sigma_group']['sigma'],
                )

                # GROUP-SPECIFIC PARAMETERS (partial pooling)
                base_elasticity = pm.Normal(
                    'base_elasticity',
                    mu=mu_global_base,
                    sigma=sigma_group_base,
                    shape=n_groups,
                )
                promo_elasticity = pm.Normal(
                    'promo_elasticity',
                    mu=mu_global_promo,
                    sigma=sigma_group_promo,
                    shape=n_groups,
                )
            else:
                # Legacy V1 global/group parameters
                mu_global_own = pm.Normal('mu_global_own',
                                          mu=self.priors['elasticity_own']['mu'],
                                          sigma=self.priors['elasticity_own']['sigma'])
                
                sigma_group_own = pm.HalfNormal('sigma_group_own',
                                               sigma=self.priors['sigma_group']['sigma'])
                
                elasticity_own = pm.Normal('elasticity_own',
                                           mu=mu_global_own,
                                           sigma=sigma_group_own,
                                           shape=n_groups)
            
            # Group-specific intercepts
            mu_global_intercept = pm.Normal('mu_global_intercept',
                                           mu=self.priors['intercept']['mu'],
                                           sigma=self.priors['intercept']['sigma'])
            
            sigma_group_intercept = pm.HalfNormal('sigma_group_intercept',
                                                 sigma=1.0)
            
            intercept = pm.Normal('intercept',
                                 mu=mu_global_intercept,
                                 sigma=sigma_group_intercept,
                                 shape=n_groups)
            
            # SHARED PARAMETERS (not group-specific)
            elasticity_cross = pm.Normal('elasticity_cross',
                                         mu=self.priors['elasticity_cross']['mu'],
                                         sigma=self.priors['elasticity_cross']['sigma'])
            
            # Linear predictor
            if use_dual:
                mu = (
                    intercept[group_idx]
                    + base_elasticity[group_idx] * X_base
                    + elasticity_cross * (X_cross * X_has_competitor)
                )
            else:
                mu = (
                    intercept[group_idx]
                    + elasticity_own[group_idx] * X_base
                    + elasticity_cross * (X_cross * X_has_competitor)
                )
            
            # Optional shared features
            if X_promo is not None:
                if use_dual:
                    mu += promo_elasticity[group_idx] * (X_promo * X_has_promo)
                else:
                    beta_promo = pm.Normal('beta_promo',
                                          mu=self.priors['beta_promo']['mu'],
                                          sigma=self.priors['beta_promo']['sigma'])
                    mu += beta_promo * (X_promo * X_has_promo)
            
            if X_spring is not None:
                beta_spring = pm.Normal('beta_spring',
                                       mu=self.priors['beta_spring']['mu'],
                                       sigma=self.priors['beta_spring']['sigma'])
                beta_summer = pm.Normal('beta_summer',
                                       mu=self.priors['beta_summer']['mu'],
                                       sigma=self.priors['beta_summer']['sigma'])
                beta_fall = pm.Normal('beta_fall',
                                     mu=self.priors['beta_fall']['mu'],
                                     sigma=self.priors['beta_fall']['sigma'])
                mu += beta_spring * X_spring + beta_summer * X_summer + beta_fall * X_fall
            
            # Likelihood
            sigma = pm.HalfNormal('sigma', sigma=self.priors['sigma']['sigma'])
            y_obs = pm.Normal('y_obs', mu=mu, sigma=sigma, observed=y)
        
        self.model = model
    
    def _sample(self):
        """Run MCMC sampling"""
        
        with self.model:
            self.trace = pm.sample(
                draws=self.n_samples,
                tune=self.n_tune,
                chains=self.n_chains,
                target_accept=self.target_accept,
                random_seed=self.random_seed,
                return_inferencedata=True,
                progressbar=self.verbose
            )


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def get_priors(prior_type: str = 'default') -> Dict:
    """Get prior specifications"""
    return PriorLibrary.get_priors(prior_type)


def fit_simple_model(data: pd.DataFrame, priors: str = 'default', **kwargs) -> BayesianResults:
    """Quick fit of simple model"""
    model = SimpleBayesianModel(priors=priors, **kwargs)
    return model.fit(data)


def fit_hierarchical_model(data: pd.DataFrame, priors: str = 'default', **kwargs) -> HierarchicalResults:
    """Quick fit of hierarchical model"""
    model = HierarchicalBayesianModel(priors=priors, **kwargs)
    return model.fit(data)
