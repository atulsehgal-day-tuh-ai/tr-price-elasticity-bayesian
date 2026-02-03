"""
Price Elasticity Data Preparation Module

Complete data transformation pipeline for Bayesian elasticity analysis.

Features:
- Loads Circana CSV files (BJ's, Sam's, Costco)
- Filters to brand-level data
- Creates log transformations
- Handles missing features (Costco-ready)
- Easy feature engineering
- Validates output quality

Usage:
    from data_prep import ElasticityDataPrep
    
    prep = ElasticityDataPrep()
    df = prep.transform('bjs.csv', 'sams.csv')
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Union, Optional, Dict, List
import logging
from dataclasses import dataclass, field


# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class PrepConfig:
    """Configuration for data preparation"""
    
    retailer_filter: str = 'All'  # 'Overall', 'All', 'BJs', 'Sams', 'Costco'
    include_seasonality: bool = True
    include_promotions: bool = True
    include_time_trend: bool = True
    log_transform_sales: bool = True
    log_transform_prices: bool = True
    brand_filters: List[str] = field(default_factory=lambda: [
        'Total Sparkling Ice Core Brand',
        'PRIVATE LABEL-BOTTLED WATER-SELTZER/SPARKLING/MINERAL WATER'
    ])
    retailers: Optional[Dict] = None
    verbose: bool = True


# ============================================================================
# MAIN DATA PREP CLASS
# ============================================================================

class ElasticityDataPrep:
    """
    Complete data preparation pipeline
    
    Transforms raw Circana data into model-ready format.
    """
    
    def __init__(self, config: Optional[PrepConfig] = None):
        """Initialize with configuration"""
        self.config = config or PrepConfig()
        self.logger = self._setup_logger()
        self.raw_data = None
        self.cleaned_data = None
        self.final_data = None
    
    def _setup_logger(self):
        """Setup logging"""
        logger = logging.getLogger('ElasticityDataPrep')
        logger.setLevel(logging.INFO if self.config.verbose else logging.WARNING)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    def transform(
        self,
        bjs_path: Union[str, Path],
        sams_path: Union[str, Path],
        costco_path: Optional[Union[str, Path]] = None
    ) -> pd.DataFrame:
        """Main transformation pipeline"""
        
        self.logger.info("="*80)
        self.logger.info("STARTING DATA TRANSFORMATION")
        self.logger.info("="*80)
        
        # Load
        self.logger.info("\nStep 1: Loading data...")
        self.raw_data = self._load_data(bjs_path, sams_path, costco_path)
        self.logger.info(f"  Loaded {len(self.raw_data)} rows")
        
        # Clean
        self.logger.info("\nStep 2: Cleaning data...")
        self.cleaned_data = self._clean_data(self.raw_data)
        self.logger.info(f"  Cleaned to {len(self.cleaned_data)} rows")
        
        # Features
        self.logger.info("\nStep 3: Creating features...")
        self.final_data = self._create_features(self.cleaned_data)
        self.logger.info(f"  Final: {len(self.final_data)} rows × {len(self.final_data.columns)} columns")
        
        # Validate
        self.logger.info("\nStep 4: Validating...")
        self._validate_output(self.final_data)
        self.logger.info("  ✓ Validation passed")
        
        self.logger.info("\n" + "="*80)
        self.logger.info("✓ TRANSFORMATION COMPLETE")
        self.logger.info("="*80)
        
        return self.final_data
    
    def _load_data(self, bjs_path, sams_path, costco_path=None) -> pd.DataFrame:
        """Load Circana CSV files"""
        
        dfs = []
        
        # BJ's
        self.logger.info("  Loading BJ's...")
        bjs = pd.read_csv(bjs_path, skiprows=2)
        bjs['Retailer'] = "BJ's"
        dfs.append(bjs)
        
        # Sam's
        self.logger.info("  Loading Sam's Club...")
        sams = pd.read_csv(sams_path, skiprows=2)
        sams['Retailer'] = "Sam's Club"
        dfs.append(sams)
        
        # Costco
        if costco_path:
            self.logger.info("  Loading Costco...")
            costco = pd.read_csv(costco_path, skiprows=2)
            costco['Retailer'] = "Costco"
            dfs.append(costco)
        
        return pd.concat(dfs, ignore_index=True)
    
    def _clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean and filter data"""
        
        df = df.copy()
        
        # Filter to brands
        df = df[df['Product'].isin(self.config.brand_filters)]
        
        # Retailer filter
        if self.config.retailer_filter == 'BJs':
            df = df[df['Retailer'] == "BJ's"]
        elif self.config.retailer_filter == 'Sams':
            df = df[df['Retailer'] == "Sam's Club"]
        elif self.config.retailer_filter == 'Costco':
            df = df[df['Retailer'] == "Costco"]
        
        # Product names
        product_map = {
            'Total Sparkling Ice Core Brand': 'Sparkling Ice',
            'PRIVATE LABEL-BOTTLED WATER-SELTZER/SPARKLING/MINERAL WATER': 'Private Label'
        }
        df['Product_Short'] = df['Product'].map(product_map)
        
        # Dates
        df['Date'] = pd.to_datetime(
            df['Time'].str.replace('Week Ending ', ''),
            format='%m-%d-%y'
        )
        
        # Prices
        df['Avg_Price'] = df['Dollar Sales'] / df['Unit Sales']
        
        # Promotions
        if self.config.include_promotions:
            promo_cols = [c for c in [
                'Unit Sales Any Merch',
                'Unit Sales Feature Only',
                'Unit Sales Display Only',
                'Unit Sales Feature and Display'
            ] if c in df.columns]
            
            if promo_cols:
                promo_sales = df[promo_cols].fillna(0).sum(axis=1)
                df['Promo_Intensity'] = (promo_sales / df['Unit Sales'].fillna(1)).clip(0, 1)
            else:
                df['Promo_Intensity'] = 0.0
        
        # Drop missing
        df = df.dropna(subset=['Dollar Sales', 'Unit Sales', 'Avg_Price'])
        
        return df
    
    def _create_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create all model features"""
        
        # Pivot
        df_wide = self._pivot_to_wide(df)
        
        # Time
        df_wide = self._add_time_features(df_wide)
        
        # Seasonality
        if self.config.include_seasonality:
            df_wide = self._add_seasonal_features(df_wide)
        
        # Logs
        if self.config.log_transform_sales:
            df_wide['Log_Unit_Sales_SI'] = np.log(df_wide['Unit_Sales_SI'])
        
        if self.config.log_transform_prices:
            df_wide['Log_Price_SI'] = np.log(df_wide['Price_SI'])
            # Competitor price may be missing for some retailers (handled downstream)
            df_wide['Log_Price_PL'] = np.log(df_wide['Price_PL'])
        
        # Clean
        df_wide = df_wide.replace([np.inf, -np.inf], np.nan)
        # Only require outcome and own price. Cross-price and promo may be missing for some retailers
        # and should be handled by model masking (via has_competitor/has_promo indicators).
        df_wide = df_wide.dropna(subset=['Log_Unit_Sales_SI', 'Log_Price_SI'])
        
        # Missing features
        if self.config.retailers:
            df_wide = self._handle_missing_features(df_wide)
        
        return df_wide
    
    def _pivot_to_wide(self, df: pd.DataFrame) -> pd.DataFrame:
        """Pivot to wide format"""
        
        index_cols = ['Date', 'Retailer'] if self.config.retailer_filter == 'All' else ['Date']
        
        # Sales
        sales = df.pivot_table(
            index=index_cols,
            columns='Product_Short',
            values='Unit Sales',
            aggfunc='sum'
        ).reset_index()
        
        # Prices
        prices = df.pivot_table(
            index=index_cols,
            columns='Product_Short',
            values='Avg_Price',
            aggfunc='mean'
        ).reset_index()
        
        # Merge
        wide = sales.merge(prices, on=index_cols, suffixes=('_sales', '_price'))
        
        # Rename
        wide = wide.rename(columns={
            'Sparkling Ice_sales': 'Unit_Sales_SI',
            'Private Label_sales': 'Unit_Sales_PL',
            'Sparkling Ice_price': 'Price_SI',
            'Private Label_price': 'Price_PL'
        })
        
        # Promo
        if self.config.include_promotions:
            promo = df[df['Product_Short'] == 'Sparkling Ice'].pivot_table(
                index=index_cols,
                values='Promo_Intensity',
                aggfunc='mean'
            ).reset_index()
            promo = promo.rename(columns={'Promo_Intensity': 'Promo_Intensity_SI'})
            wide = wide.merge(promo, on=index_cols, how='left')
            wide['Promo_Intensity_SI'] = wide['Promo_Intensity_SI'].fillna(0)
        
        return wide
    
    def _add_time_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add time features"""
        
        df = df.sort_values('Date').reset_index(drop=True)
        
        if self.config.include_time_trend:
            min_date = df['Date'].min()
            df['Week_Number'] = ((df['Date'] - min_date).dt.days / 7).astype(int)
        
        return df
    
    def _add_seasonal_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add seasonal dummies"""
        
        df['Month'] = df['Date'].dt.month
        df['Spring'] = df['Month'].isin([3, 4, 5]).astype(int)
        df['Summer'] = df['Month'].isin([6, 7, 8]).astype(int)
        df['Fall'] = df['Month'].isin([9, 10, 11]).astype(int)
        
        return df
    
    def _handle_missing_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Handle retailer-specific missing features"""
        
        if 'Retailer' not in df.columns:
            return df

        def _norm(s: str) -> str:
            # normalize retailer labels to match config keys robustly
            return (
                str(s)
                .lower()
                .replace("'", "")
                .replace("’", "")
                .replace(".", "")
                .replace("-", " ")
                .replace("&", "and")
                .strip()
            )

        # Normalize config keys once
        cfg_by_norm = {_norm(k): v for k, v in (self.config.retailers or {}).items()}

        # Default availability flags to "present"; retailer configs can override.
        # These flags allow the model to include/exclude terms without introducing NaNs.
        if 'has_promo' not in df.columns:
            df['has_promo'] = 1
        if 'has_competitor' not in df.columns:
            df['has_competitor'] = 1

        for retailer_value in df['Retailer'].dropna().unique():
            cfg = cfg_by_norm.get(_norm(retailer_value))
            if cfg is None:
                # common aliases
                aliases = {
                    "bjs": ["bjs", "bj s", "bjs wholesale", "bjs wholesale club"],
                    "sams": ["sams", "sams club", "sams club wholesale", "sams club inc"],
                    "costco": ["costco", "costco wholesale", "costco wholesale corp"],
                }
                norm_val = _norm(retailer_value)
                match_key = None
                for canonical, a_list in aliases.items():
                    if norm_val in a_list:
                        # find first config entry that matches any alias string
                        for alias in a_list:
                            if alias in cfg_by_norm:
                                match_key = alias
                                break
                    if match_key:
                        break
                if match_key:
                    cfg = cfg_by_norm.get(match_key)

            if cfg is None:
                # no retailer-specific config; default to "features present"
                cfg = {}

            mask = df['Retailer'] == retailer_value

            if not cfg.get('has_promo', True):
                # Use safe numeric default + availability indicator.
                # The model masks promo effect via `has_promo`.
                if 'Promo_Intensity_SI' in df.columns:
                    df.loc[mask, 'Promo_Intensity_SI'] = 0.0
                df.loc[mask, 'has_promo'] = 0
            else:
                df.loc[mask, 'has_promo'] = 1

            if not cfg.get('has_competitor', True):
                # Use safe numeric default + availability indicator.
                # The model masks cross-price effect via `has_competitor`.
                if 'Price_PL' in df.columns:
                    df.loc[mask, 'Price_PL'] = 0.0
                if 'Log_Price_PL' in df.columns:
                    df.loc[mask, 'Log_Price_PL'] = 0.0
                df.loc[mask, 'has_competitor'] = 0
            else:
                df.loc[mask, 'has_competitor'] = 1
        
        return df
    
    def _validate_output(self, df: pd.DataFrame):
        """Validate output"""
        
        required = ['Date', 'Log_Unit_Sales_SI', 'Log_Price_SI']
        
        if self.config.include_promotions:
            required.append('Promo_Intensity_SI')
        
        if self.config.include_seasonality:
            required.extend(['Spring', 'Summer', 'Fall'])
        
        if self.config.retailer_filter == 'All':
            required.append('Retailer')
            if self.config.retailers:
                required.extend(['has_promo', 'has_competitor'])

        # Cross price is generally required, but allow it to be missing for some retailers
        # if retailer-specific configuration indicates missing competitor data.
        if 'Log_Price_PL' in df.columns:
            required.append('Log_Price_PL')
        else:
            # if not present at all, that is a structural problem
            raise ValueError("Missing column: Log_Price_PL (competitor price log).")
        
        missing = set(required) - set(df.columns)
        if missing:
            raise ValueError(f"Missing columns: {missing}")
        
        if len(df) < 30:
            raise ValueError(f"Insufficient data: {len(df)} rows")
    
    # ========================================================================
    # FEATURE ENGINEERING
    # ========================================================================
    
    def add_interaction_term(self, df: pd.DataFrame, var1: str, var2: str, name: str = None) -> pd.DataFrame:
        """Add interaction term"""
        if name is None:
            name = f"{var1}_x_{var2}"
        df[name] = df[var1] * df[var2]
        if self.config.verbose:
            self.logger.info(f"  Added interaction: {name}")
        return df
    
    def add_lagged_feature(self, df: pd.DataFrame, var: str, lags: List[int], group_by: List[str] = None) -> pd.DataFrame:
        """Add lagged features"""
        df = df.sort_values('Date')
        for lag in lags:
            lag_name = f"{var}_lag{lag}"
            if group_by:
                df[lag_name] = df.groupby(group_by)[var].shift(lag)
            else:
                df[lag_name] = df[var].shift(lag)
            if self.config.verbose:
                self.logger.info(f"  Added lag: {lag_name}")
        return df
    
    def add_moving_average(self, df: pd.DataFrame, var: str, windows: List[int], group_by: List[str] = None) -> pd.DataFrame:
        """Add moving averages"""
        df = df.sort_values('Date')
        for window in windows:
            ma_name = f"{var}_ma{window}"
            if group_by:
                df[ma_name] = df.groupby(group_by)[var].transform(
                    lambda x: x.rolling(window=window, min_periods=1).mean()
                )
            else:
                df[ma_name] = df[var].rolling(window=window, min_periods=1).mean()
            if self.config.verbose:
                self.logger.info(f"  Added MA: {ma_name}")
        return df
    
    def add_custom_feature(self, df: pd.DataFrame, name: str, formula) -> pd.DataFrame:
        """Add custom feature"""
        df[name] = formula(df)
        if self.config.verbose:
            self.logger.info(f"  Added custom: {name}")
        return df
    
    # ========================================================================
    # UTILITIES
    # ========================================================================
    
    def get_summary_stats(self) -> pd.DataFrame:
        """Get summary statistics"""
        if self.final_data is None:
            raise ValueError("No data. Run transform() first.")
        return self.final_data.describe()
    
    def export_csv(self, path: str):
        """Export to CSV"""
        if self.final_data is None:
            raise ValueError("No data. Run transform() first.")
        self.final_data.to_csv(path, index=False)
        self.logger.info(f"Exported to {path}")


# ============================================================================
# CONVENIENCE FUNCTION
# ============================================================================

def quick_prep(
    bjs_path: str,
    sams_path: str,
    costco_path: Optional[str] = None,
    retailer_filter: str = 'All',
    **kwargs
) -> pd.DataFrame:
    """Quick data preparation"""
    config = PrepConfig(retailer_filter=retailer_filter, **kwargs)
    prep = ElasticityDataPrep(config)
    return prep.transform(bjs_path, sams_path, costco_path)
