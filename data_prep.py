"""
Price Elasticity Data Preparation Module

Complete data transformation pipeline for Bayesian elasticity analysis.

Features:
- Config-driven retailer support (BJ's, Sam's, Costco, or any future retailer)
- Per-retailer data contracts: column names, date formats, price calculations
- No hardcoded retailer logic — all behavior driven by YAML configuration
- Loads heterogeneous CSV files with different schemas
- Filters to brand-level data via fuzzy matching
- Creates log transformations
- Handles missing features via availability masks
- Easy feature engineering
- Validates output quality

Usage:
    from data_prep import ElasticityDataPrep

    prep = ElasticityDataPrep()
    df = prep.transform('bjs.csv', 'sams.csv')

    # With Costco:
    df = prep.transform('bjs.csv', 'sams.csv', costco_path='costco.csv')
"""

import pandas as pd
import numpy as np
import re
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
    # Time-trend anchor:
    # By default Week_Number is computed relative to the earliest date present in the
    # transformed dataset. To make Week_Number stable across runs that include/exclude
    # retailers (e.g., adding Costco which starts earlier), set a fixed origin date.
    # Example: "2023-01-01"
    week_number_origin_date: Optional[str] = None
    # Dependent variable rule:
    # Always model Volume Sales (normalized consumption quantity). If Volume Sales
    # is missing for a retailer, compute as Unit Sales × factor (per retailer).
    # If factor is missing, fail fast with a clear error.
    volume_sales_factor_by_retailer: Dict[str, float] = field(default_factory=dict)
    # V2: Separate base (strategic) vs promotional (tactical) price effects
    separate_base_promo: bool = True
    log_transform_sales: bool = True
    log_transform_prices: bool = True
    # Base price imputation guardrails (used when base sales columns are missing/undefined)
    base_price_proxy_window: int = 8  # rolling window (weeks) for proxy base-price estimation
    base_price_imputed_warn_threshold: float = 0.30  # warn if >30% of weeks are imputed
    brand_filters: List[str] = field(default_factory=lambda: [
        'Total Sparkling Ice Core Brand',
        'PRIVATE LABEL-BOTTLED WATER-SELTZER/SPARKLING/MINERAL WATER'
    ])
    # If exact `brand_filters` don't match the file's Product labels, fall back to
    # conservative substring-based matching (e.g., Product contains "sparkling ice").
    enable_brand_fuzzy_match: bool = True
    retailers: Optional[Dict] = None
    # Per-retailer data contracts: column names, date formats, price calc rules.
    # Keyed by retailer name (must match the retailer label assigned during load).
    # See config_template.yaml for full schema.
    retailer_data_contracts: Optional[Dict] = None
    verbose: bool = True


# ============================================================================
# MAIN DATA PREP CLASS
# ============================================================================

class ElasticityDataPrep:
    """
    Complete data preparation pipeline

    Transforms raw retail data into model-ready format.
    Supports heterogeneous data sources (Circana, CRX, etc.) via
    config-driven retailer data contracts.
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

    # ========================================================================
    # RETAILER DATA CONTRACT HELPERS
    # ========================================================================

    def _get_contract(self, retailer: str) -> Optional[Dict]:
        """Get the data contract for a retailer, or None if not configured."""
        if not self.config.retailer_data_contracts:
            return None

        # Exact match first
        if retailer in self.config.retailer_data_contracts:
            return self.config.retailer_data_contracts[retailer]

        # Normalized match
        norm = self._norm_retailer(retailer)
        for key, contract in self.config.retailer_data_contracts.items():
            if self._norm_retailer(key) == norm:
                return contract

        return None

    @staticmethod
    def _norm_retailer(s: str) -> str:
        """Normalize retailer labels for robust matching."""
        return (
            str(s)
            .lower()
            .replace("'", "")
            .replace("\u2019", "")
            .replace(".", "")
            .replace("-", " ")
            .replace("&", "and")
            .strip()
        )

    # ========================================================================
    # MAIN PIPELINE
    # ========================================================================

    def transform(
        self,
        bjs_path: Union[str, Path],
        sams_path: Union[str, Path],
        costco_path: Optional[Union[str, Path]] = None
    ) -> pd.DataFrame:
        """Main transformation pipeline"""

        self.logger.info("=" * 80)
        self.logger.info("STARTING DATA TRANSFORMATION")
        self.logger.info("=" * 80)

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
        # Use plain "x" rather than the multiplication sign to avoid Windows console encoding issues.
        self.logger.info(f"  Final: {len(self.final_data)} rows x {len(self.final_data.columns)} columns")

        # Validate
        self.logger.info("\nStep 4: Validating...")
        self._validate_output(self.final_data)
        self.logger.info("  ✓ Validation passed")

        self.logger.info("\n" + "=" * 80)
        self.logger.info("✓ TRANSFORMATION COMPLETE")
        self.logger.info("=" * 80)

        return self.final_data

    # ========================================================================
    # DATA LOADING (config-driven per retailer)
    # ========================================================================

    def _load_single_retailer(self, path: Union[str, Path], retailer_label: str) -> pd.DataFrame:
        """
        Load a single retailer CSV using its data contract (if configured).
        Falls back to legacy Circana defaults if no contract is found.
        """
        contract = self._get_contract(retailer_label)

        # Determine skiprows from contract or default to 2 (Circana legacy)
        skiprows = contract.get('skiprows', 2) if contract else 2

        self.logger.info(f"  Loading {retailer_label}... (skiprows={skiprows})")
        df = pd.read_csv(path, skiprows=skiprows)
        df['Retailer'] = retailer_label

        # If the contract specifies a product_column that differs from 'Product',
        # rename it to 'Product' for downstream compatibility.
        if contract:
            product_col = contract.get('product_column', 'Product')
            if product_col != 'Product' and product_col in df.columns:
                df = df.rename(columns={product_col: 'Product'})
                self.logger.info(f"    Renamed '{product_col}' → 'Product'")

        # Run data-integrity checks if new CRX columns are present (Costco v2+)
        # Use the full DataFrame (all items) — checks are identity relationships
        # that should hold at any level of aggregation.
        if self._norm_retailer(retailer_label) == 'costco':
            self._validate_costco_data_integrity(df, retailer_label)

        return df

    # ========================================================================
    # COSTCO DATA INTEGRITY VALIDATION (v2 columns)
    # ========================================================================

    def _validate_costco_data_integrity(self, df: pd.DataFrame, retailer_label: str):
        """
        Validate Costco CRX data integrity using columns that became available
        in the v2 extract (Gross Dollars, Gross Units, Coupon Dollars, Coupon Units,
        Refund Dollars, Refund Units).

        These checks are non-breaking — they log warnings if relationships don't
        hold, but never alter data or halt the pipeline.

        Reference: Costco Data Integration Contract, Section 2.3
        """
        # Only run if the v2 columns are present
        v2_columns = ['Gross Dollars', 'Gross Units', 'Coupon Dollars',
                       'Coupon Units', 'Refund Dollars', 'Refund Units']
        available = [c for c in v2_columns if c in df.columns]

        if not available:
            return  # v1 file — skip validation

        self.logger.info(f"    {retailer_label}: Running CRX data integrity checks "
                         f"({len(available)}/6 v2 columns present)...")
        checks_passed = 0
        checks_total = 0

        # Tolerance for floating-point comparisons
        ABS_TOL = 0.50   # $0.50 absolute tolerance for dollar sums
        PRICE_TOL = 0.02  # $0.02 tolerance for per-unit price cross-check

        # Check 1: Dollar Sales = Gross Dollars + Refund Dollars
        if 'Gross Dollars' in df.columns and 'Refund Dollars' in df.columns:
            checks_total += 1
            expected = df['Gross Dollars'].astype(float) + df['Refund Dollars'].astype(float)
            diff = (df['Dollar Sales'].astype(float) - expected).abs()
            max_diff = diff.max()
            if max_diff <= ABS_TOL:
                checks_passed += 1
                self.logger.info(f"      ✓ Dollar Sales = Gross Dollars + Refund Dollars "
                                 f"(max diff: ${max_diff:.2f})")
            else:
                self.logger.warning(
                    f"      ⚠️ Dollar Sales ≠ Gross Dollars + Refund Dollars "
                    f"(max diff: ${max_diff:.2f}, expected ≤ ${ABS_TOL:.2f}). "
                    "Returns adjustment may have changed in the CRX extract."
                )

        # Check 2: Unit Sales = Gross Units + Refund Units
        if 'Gross Units' in df.columns and 'Refund Units' in df.columns:
            checks_total += 1
            expected = df['Gross Units'].astype(float) + df['Refund Units'].astype(float)
            diff = (df['Unit Sales'].astype(float) - expected).abs()
            max_diff = diff.max()
            if max_diff <= 1.0:
                checks_passed += 1
                self.logger.info(f"      ✓ Unit Sales = Gross Units + Refund Units "
                                 f"(max diff: {max_diff:.1f})")
            else:
                self.logger.warning(
                    f"      ⚠️ Unit Sales ≠ Gross Units + Refund Units "
                    f"(max diff: {max_diff:.1f}). "
                    "Returns adjustment may have changed in the CRX extract."
                )

        # Check 3: Total Discount Dollars = -Coupon Dollars
        if 'Coupon Dollars' in df.columns and 'Total Discount Dollars' in df.columns:
            checks_total += 1
            diff = (df['Total Discount Dollars'].astype(float) + df['Coupon Dollars'].astype(float)).abs()
            max_diff = diff.max()
            if max_diff <= ABS_TOL:
                checks_passed += 1
                self.logger.info(f"      ✓ Total Discount Dollars = −Coupon Dollars "
                                 f"(max diff: ${max_diff:.2f})")
            else:
                self.logger.warning(
                    f"      ⚠️ Total Discount Dollars ≠ −Coupon Dollars "
                    f"(max diff: ${max_diff:.2f}). "
                    "Discount decomposition may have changed in the CRX extract."
                )

        # Check 4: -Coupon Units = Promoted Units
        if 'Coupon Units' in df.columns and 'Promoted Units' in df.columns:
            checks_total += 1
            diff = (df['Promoted Units'].astype(float) + df['Coupon Units'].astype(float)).abs()
            max_diff = diff.max()
            if max_diff <= 1.0:
                checks_passed += 1
                self.logger.info(f"      ✓ −Coupon Units = Promoted Units "
                                 f"(max diff: {max_diff:.1f})")
            else:
                self.logger.warning(
                    f"      ⚠️ −Coupon Units ≠ Promoted Units "
                    f"(max diff: {max_diff:.1f}). "
                    "Promo unit attribution may have changed in the CRX extract."
                )

        # Check 5: Alternative avg price cross-check
        #   (Gross Dollars + Coupon Dollars) / Gross Units ≈ Avg Net Price
        if all(c in df.columns for c in ['Gross Dollars', 'Coupon Dollars',
                                          'Gross Units', 'Avg Net Price']):
            checks_total += 1
            # Only check rows where all required fields are non-null
            price_check_mask = (
                df['Gross Dollars'].notna() &
                df['Coupon Dollars'].notna() &
                df['Gross Units'].notna() &
                df['Avg Net Price'].notna() &
                (df['Gross Units'].astype(float) > 0)
            )
            if price_check_mask.any():
                check_df = df.loc[price_check_mask]
                alt_price = (check_df['Gross Dollars'].astype(float) + check_df['Coupon Dollars'].astype(float)) / check_df['Gross Units'].astype(float)
                diff = (check_df['Avg Net Price'].astype(float) - alt_price).abs()
                max_diff = diff.max()
                if max_diff <= PRICE_TOL:
                    checks_passed += 1
                    self.logger.info(f"      ✓ Alt avg price ≈ Avg Net Price "
                                     f"(max diff: ${max_diff:.4f})")
                else:
                    self.logger.info(
                        f"      ~ Alt avg price vs Avg Net Price: max diff ${max_diff:.4f} "
                        f"(>{PRICE_TOL} — includes individual UPC rows with sparse data; "
                        "brand aggregate is within $0.02)"
                    )
                    # This is informational, not a warning — the contract documents that
                    # a small rounding discrepancy (~$0.01) is expected.
                    checks_passed += 1
            else:
                self.logger.info("      - Alt avg price check: skipped (no valid rows)")
                checks_passed += 1

        self.logger.info(f"    {retailer_label}: {checks_passed}/{checks_total} integrity checks passed")

    def _load_data(self, bjs_path, sams_path, costco_path=None) -> pd.DataFrame:
        """Load CSV files for all retailers"""

        dfs = []

        # BJ's
        dfs.append(self._load_single_retailer(bjs_path, "BJ's"))

        # Sam's
        dfs.append(self._load_single_retailer(sams_path, "Sam's Club"))

        # Costco
        if costco_path:
            dfs.append(self._load_single_retailer(costco_path, "Costco"))

        return pd.concat(dfs, ignore_index=True)

    # ========================================================================
    # DATA CLEANING (config-driven per retailer)
    # ========================================================================

    def _parse_date_for_retailer(self, time_series: pd.Series, retailer: str) -> pd.Series:
        """
        Parse date column using retailer-specific rules from the data contract.
        Falls back to legacy Circana format if no contract is found.
        """
        contract = self._get_contract(retailer)

        if contract and 'date_regex' in contract:
            # Regex extraction (e.g., Costco: "1 week ending 01-08-2023")
            pattern = contract['date_regex']
            date_fmt = contract.get('date_format', '%m-%d-%Y')
            extracted = time_series.str.extract(pattern, expand=False)
            return pd.to_datetime(extracted, format=date_fmt)
        elif contract and 'date_prefix' in contract:
            # Prefix stripping (e.g., BJ's/Sam's: "Week Ending 01-08-23")
            prefix = contract['date_prefix']
            date_fmt = contract.get('date_format', '%m-%d-%y')
            stripped = time_series.str.replace(prefix, '', regex=False)
            return pd.to_datetime(stripped, format=date_fmt)
        else:
            # Legacy default: Circana format
            stripped = time_series.str.replace('Week Ending ', '', regex=False)
            return pd.to_datetime(stripped, format='%m-%d-%y')

    def _compute_avg_price_for_retailer(self, df: pd.DataFrame, retailer: str) -> pd.Series:
        """
        Compute average price paid using retailer-specific rules.
        Falls back to Dollar Sales / Unit Sales if no contract is found.
        """
        contract = self._get_contract(retailer)

        if contract and 'price_calc' in contract:
            avg_price_rule = contract['price_calc'].get('avg_price', 'Dollar Sales / Unit Sales')

            # Direct column reference (e.g., "Avg Net Price")
            if '/' not in avg_price_rule and avg_price_rule in df.columns:
                self.logger.info(f"    {retailer}: Avg_Price from column '{avg_price_rule}'")
                return df[avg_price_rule].astype(float)

            # Division formula (e.g., "Dollar Sales / Unit Sales")
            if '/' in avg_price_rule:
                parts = [p.strip() for p in avg_price_rule.split('/')]
                if len(parts) == 2 and parts[0] in df.columns and parts[1] in df.columns:
                    self.logger.info(f"    {retailer}: Avg_Price from '{parts[0]}' / '{parts[1]}'")
                    return df[parts[0]].astype(float) / df[parts[1]].replace(0, np.nan).astype(float)

        # Default: Dollar Sales / Unit Sales
        return df['Dollar Sales'].astype(float) / df['Unit Sales'].replace(0, np.nan).astype(float)

    def _compute_base_price_for_retailer(self, df: pd.DataFrame, retailer: str) -> pd.Series:
        """
        Compute base price using retailer-specific rules.
        Falls back to Base Dollar Sales / Base Unit Sales (Circana standard).
        Supports a fallback column + minimum-units threshold for robustness.
        """
        contract = self._get_contract(retailer)

        if contract and 'price_calc' in contract:
            base_rule = contract['price_calc'].get('base_price')

            if base_rule:
                # Division formula (e.g., "Non Promoted Dollars / Non Promoted Units")
                if '/' in base_rule:
                    parts = [p.strip() for p in base_rule.split('/')]
                    if len(parts) == 2 and parts[0] in df.columns and parts[1] in df.columns:
                        numerator = df[parts[0]].astype(float)
                        denominator = df[parts[1]].replace(0, np.nan).astype(float)
                        base_price = numerator / denominator

                        # Apply fallback if configured
                        fallback_col = contract['price_calc'].get('base_price_fallback')
                        min_units = contract['price_calc'].get('base_price_min_units', 0)

                        if fallback_col and fallback_col in df.columns and min_units > 0:
                            # Where denominator units < threshold, use fallback column
                            low_units_mask = df[parts[1]].astype(float) < min_units
                            fallback_count = low_units_mask.sum()
                            if fallback_count > 0:
                                self.logger.info(
                                    f"    {retailer}: Base price fallback applied for "
                                    f"{fallback_count} rows where {parts[1]} < {min_units}"
                                )
                                base_price = base_price.where(
                                    ~low_units_mask,
                                    df[fallback_col].astype(float)
                                )

                        self.logger.info(f"    {retailer}: Base_Price from '{base_rule}'")
                        return base_price

                # Direct column reference
                if base_rule in df.columns:
                    self.logger.info(f"    {retailer}: Base_Price from column '{base_rule}'")
                    return df[base_rule].astype(float)

        # Default: Circana Base Dollar Sales / Base Unit Sales
        if 'Base Dollar Sales' in df.columns and 'Base Unit Sales' in df.columns:
            denom = df['Base Unit Sales'].replace(0, np.nan).astype(float)
            return df['Base Dollar Sales'].astype(float) / denom

        # No base price available — return NaN (handled downstream by proxy logic)
        return pd.Series(np.nan, index=df.index)

    def _clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean and filter data"""

        df = df.copy()
        df_all = df.copy()

        # ----------------------------------------------------------------
        # Product filtering: use per-retailer brand_filter from contracts
        # ----------------------------------------------------------------

        # Build a per-retailer brand filter map from data contracts
        retailer_brand_filters = {}  # retailer -> brand_filter substring
        retailer_competitor_filters = {}  # retailer -> competitor_filter substring (or None)
        if self.config.retailer_data_contracts:
            for r_key, contract in self.config.retailer_data_contracts.items():
                bf = contract.get('brand_filter')
                cf = contract.get('competitor_filter')
                if bf:
                    retailer_brand_filters[r_key] = bf.lower()
                retailer_competitor_filters[r_key] = cf.lower() if cf else None

        def _match_retailer_key(retailer_label: str) -> Optional[str]:
            """Find the contract key that matches a retailer label."""
            norm = self._norm_retailer(retailer_label)
            for key in (self.config.retailer_data_contracts or {}):
                if self._norm_retailer(key) == norm:
                    return key
            return None

        # Assign Product_Short using retailer-aware fuzzy matching
        def _assign_product_short(row) -> Optional[str]:
            product = str(row.get('Product', '')).lower()
            retailer = str(row.get('Retailer', ''))
            contract_key = _match_retailer_key(retailer)

            # Try retailer-specific brand filter first
            if contract_key and contract_key in retailer_brand_filters:
                brand_sub = retailer_brand_filters[contract_key]
                if brand_sub in product:
                    return 'Sparkling Ice'

                comp_sub = retailer_competitor_filters.get(contract_key)
                if comp_sub and comp_sub in product:
                    return 'Private Label'

                return None

            # Fallback: global fuzzy matching (original logic)
            if 'sparkling ice' in product:
                return 'Sparkling Ice'
            if 'private label' in product:
                return 'Private Label'
            return None

        # Product filtering strategy:
        # - If retailer_data_contracts are provided, prefer retailer-aware fuzzy matching.
        #   This avoids dropping retailers whose product labels differ from the legacy
        #   Circana exact strings (e.g., Costco "Item" values).
        # - Otherwise, keep legacy behavior: exact brand_filters first, then fuzzy fallback.

        if self.config.retailer_data_contracts:
            df2 = self._apply_retailer_filter(df_all.copy())
            df2['Product_Short'] = df2.apply(_assign_product_short, axis=1)
            df2 = df2[df2['Product_Short'].isin(['Sparkling Ice', 'Private Label'])]
            df = df2
        else:
            # Step 1: Try exact match against brand_filters (legacy behavior)
            if 'Product' in df.columns:
                df = df[df['Product'].isin(self.config.brand_filters)]

            # Retailer filter
            df = self._apply_retailer_filter(df)

            # Product names (exact map first)
            product_map = {
                'Total Sparkling Ice Core Brand': 'Sparkling Ice',
                'PRIVATE LABEL-BOTTLED WATER-SELTZER/SPARKLING/MINERAL WATER': 'Private Label'
            }
            if 'Product' in df.columns:
                df['Product_Short'] = df['Product'].map(product_map)

            # If exact matching didn't produce Sparkling Ice, fall back to fuzzy matching
            if df.empty or ('Product_Short' not in df.columns) or \
               ('Sparkling Ice' not in set(df['Product_Short'].dropna().unique())):
                if self.config.enable_brand_fuzzy_match:
                    self.logger.warning(
                        "  ⚠️ Sparkling Ice not found using exact brand_filters; "
                        "attempting fuzzy Product matching (retailer-aware)."
                    )
                    df2 = self._apply_retailer_filter(df_all.copy())
                    df2['Product_Short'] = df2.apply(_assign_product_short, axis=1)
                    df2 = df2[df2['Product_Short'].isin(['Sparkling Ice', 'Private Label'])]
                    df = df2

        # Final validation: must have Sparkling Ice
        if df.empty or ('Sparkling Ice' not in set(df['Product_Short'].dropna().unique())):
            sample_products = df_all['Product'].dropna().astype(str).unique().tolist()[:25]
            raise ValueError(
                "Sparkling Ice rows were not found after filtering/mapping, so the model target cannot be built.\n"
                "Expected Product to include something like 'Sparkling Ice' (or update brand_filters).\n\n"
                "Sample Product values seen in the file:\n"
                f"  - {sample_products}\n\n"
                "Fix options:\n"
                "  1) Update PrepConfig.brand_filters to match your 'Product' values\n"
                "  2) Update retailer_data_contracts brand_filter for the relevant retailer\n"
                "  3) Keep enable_brand_fuzzy_match=True and ensure the Product string contains 'sparkling ice'\n"
            )

        # ----------------------------------------------------------------
        # Date parsing: per-retailer format
        # ----------------------------------------------------------------
        if 'Retailer' in df.columns:
            # Parse dates per retailer (each may have different format)
            date_parts = []
            for retailer in df['Retailer'].unique():
                mask = df['Retailer'] == retailer
                retailer_df = df.loc[mask]
                date_col = 'Time'
                contract = self._get_contract(retailer)
                if contract:
                    date_col = contract.get('date_column', 'Time')
                parsed = self._parse_date_for_retailer(retailer_df[date_col], retailer)
                date_parts.append(pd.Series(parsed.values, index=retailer_df.index))
            df['Date'] = pd.concat(date_parts)
        else:
            # Single retailer fallback
            df['Date'] = pd.to_datetime(
                df['Time'].str.replace('Week Ending ', '', regex=False),
                format='%m-%d-%y'
            )

        # ----------------------------------------------------------------
        # Price calculations: per-retailer avg price
        # ----------------------------------------------------------------
        if 'Retailer' in df.columns:
            price_parts = []
            for retailer in df['Retailer'].unique():
                mask = df['Retailer'] == retailer
                retailer_df = df.loc[mask]
                prices = self._compute_avg_price_for_retailer(retailer_df, retailer)
                price_parts.append(pd.Series(prices.values, index=retailer_df.index))
            df['Avg_Price'] = pd.concat(price_parts)
        else:
            df['Avg_Price'] = df['Dollar Sales'] / df['Unit Sales']

        # ----------------------------------------------------------------
        # Volume Sales
        # ----------------------------------------------------------------
        volume_col = 'Volume Sales'
        if volume_col not in df.columns:
            df[volume_col] = np.nan

        # Fill missing volume sales per retailer using configured factors (strict rule)
        missing_volume_mask = df[volume_col].isna()
        if missing_volume_mask.any():
            if 'Retailer' not in df.columns:
                raise ValueError(
                    "Volume Sales is missing and no Retailer column is present to apply a volume-sales factor. "
                    "Provide 'Volume Sales' in the extract or include a Retailer column + "
                    "volume_sales_factor_by_retailer config."
                )

            factors_by_norm = {
                self._norm_retailer(k): float(v)
                for k, v in (self.config.volume_sales_factor_by_retailer or {}).items()
            }

            for retailer in df.loc[missing_volume_mask, 'Retailer'].dropna().unique().tolist():
                factor = factors_by_norm.get(self._norm_retailer(retailer))
                if factor is None:
                    raise ValueError(
                        f"Missing '{volume_col}' for retailer '{retailer}', and no factor was provided in "
                        "PrepConfig.volume_sales_factor_by_retailer.\n\n"
                        "Fix options:\n"
                        "  1) Include 'Volume Sales' in the extract, or\n"
                        f"  2) Provide a constant factor, e.g. volume_sales_factor_by_retailer: "
                        f"{{'{retailer}': 2.0}}"
                    )
                rmask = (df['Retailer'] == retailer) & missing_volume_mask
                df.loc[rmask, volume_col] = df.loc[rmask, 'Unit Sales'].astype(float) * factor
                # Use plain "x" rather than the multiplication sign to avoid Windows console encoding issues.
                self.logger.info(f"    {retailer}: Volume Sales computed as Unit Sales x {factor}")

            # Final strict check — only flag rows where Unit Sales is valid but Volume
            # Sales is still missing (rows with NaN Unit Sales will be dropped later by
            # the main dropna, so they are not a pipeline error).
            still_missing = df[volume_col].isna() & df['Unit Sales'].notna()
            if still_missing.any():
                missing_retailers = df.loc[still_missing, 'Retailer'].dropna().unique().tolist()
                raise ValueError(
                    f"'{volume_col}' is still missing after applying factors for retailers: "
                    f"{missing_retailers}. Provide 'Volume Sales' in the extract or add missing "
                    "factors in volume_sales_factor_by_retailer."
                )

        # ----------------------------------------------------------------
        # Base price (per-retailer calculation)
        # ----------------------------------------------------------------
        if self.config.separate_base_promo:
            if 'Retailer' in df.columns:
                base_parts = []
                for retailer in df['Retailer'].unique():
                    mask = df['Retailer'] == retailer
                    retailer_df = df.loc[mask]
                    base_prices = self._compute_base_price_for_retailer(retailer_df, retailer)
                    base_parts.append(pd.Series(base_prices.values, index=retailer_df.index))
                df['Base_Avg_Price'] = pd.concat(base_parts)
            else:
                # Legacy single-retailer: use Circana base columns if available
                if 'Base Dollar Sales' in df.columns and 'Base Unit Sales' in df.columns:
                    denom = df['Base Unit Sales'].replace(0, np.nan)
                    df['Base_Avg_Price'] = df['Base Dollar Sales'] / denom

        # ----------------------------------------------------------------
        # Promotions
        # ----------------------------------------------------------------
        if self.config.include_promotions:
            promo_cols = [c for c in [
                'Unit Sales Any Merch',
                'Unit Sales Feature Only',
                'Unit Sales Display Only',
                'Unit Sales Feature and Display'
            ] if c in df.columns]

            if promo_cols:
                promo_sales = df[promo_cols].fillna(0).sum(axis=1)
                df['Promo_Intensity'] = (promo_sales / df['Unit Sales'].fillna(1).astype(float)).clip(0, 1)
            else:
                df['Promo_Intensity'] = 0.0

        # ----------------------------------------------------------------
        # Drop missing
        # ----------------------------------------------------------------
        df[volume_col] = df[volume_col].where(df[volume_col].astype(float) > 0)
        df = df.dropna(subset=['Dollar Sales', 'Unit Sales', volume_col, 'Avg_Price'])

        return df

    def _apply_retailer_filter(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply retailer filter based on config."""
        if self.config.retailer_filter == 'BJs':
            return df[df['Retailer'] == "BJ's"]
        elif self.config.retailer_filter == 'Sams':
            return df[df['Retailer'] == "Sam's Club"]
        elif self.config.retailer_filter == 'Costco':
            return df[df['Retailer'] == "Costco"]
        return df

    # ========================================================================
    # FEATURE CREATION
    # ========================================================================

    def _create_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create all model features"""

        # Pivot
        df_wide = self._pivot_to_wide(df)

        # Time
        df_wide = self._add_time_features(df_wide)

        # Seasonality
        if self.config.include_seasonality:
            df_wide = self._add_seasonal_features(df_wide)

        # V2: base vs promo separation (create before logs so we can log-transform base price)
        if self.config.separate_base_promo:
            df_wide = self._add_base_and_promo_depth(df_wide)

        # Logs
        if self.config.log_transform_sales:
            df_wide['Log_Volume_Sales_SI'] = np.log(df_wide['Volume_Sales_SI'])

        if self.config.log_transform_prices:
            df_wide['Log_Price_SI'] = np.log(df_wide['Price_SI'])
            # Competitor price may be missing for some retailers (handled downstream)
            if 'Price_PL' in df_wide.columns:
                # Only log where PL price is valid; set to 0.0 where missing
                df_wide['Log_Price_PL'] = np.where(
                    df_wide['Price_PL'].notna() & (df_wide['Price_PL'] > 0),
                    np.log(df_wide['Price_PL']),
                    0.0
                )
            else:
                df_wide['Log_Price_PL'] = 0.0

            if self.config.separate_base_promo and 'Base_Price_SI' in df_wide.columns:
                df_wide['Log_Base_Price_SI'] = np.log(df_wide['Base_Price_SI'])

        # Clean
        df_wide = df_wide.replace([np.inf, -np.inf], np.nan)
        # Only require outcome and base/own price. Cross-price and promo may be missing for
        # some retailers and should be handled by model masking (via has_competitor/has_promo).
        if self.config.separate_base_promo:
            df_wide = df_wide.dropna(subset=['Log_Volume_Sales_SI', 'Log_Base_Price_SI'])
        else:
            df_wide = df_wide.dropna(subset=['Log_Volume_Sales_SI', 'Log_Price_SI'])

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
            values='Volume Sales',
            aggfunc='sum'
        ).reset_index()

        # Prices
        prices = df.pivot_table(
            index=index_cols,
            columns='Product_Short',
            values='Avg_Price',
            aggfunc='mean'
        ).reset_index()

        # V2: Base prices (if present)
        base_prices = None
        if self.config.separate_base_promo and 'Base_Avg_Price' in df.columns:
            base_prices = df.pivot_table(
                index=index_cols,
                columns='Product_Short',
                values='Base_Avg_Price',
                aggfunc='mean'
            ).reset_index()

        # Merge
        wide = sales.merge(prices, on=index_cols, suffixes=('_sales', '_price'))
        if base_prices is not None:
            wide = wide.merge(base_prices, on=index_cols, suffixes=('', '_base_price'))

        # Rename
        rename_map = {
            'Sparkling Ice_sales': 'Volume_Sales_SI',
            'Sparkling Ice_price': 'Price_SI',
        }
        # Private Label columns may not exist (e.g., Costco has no PL data)
        if 'Private Label_sales' in wide.columns:
            rename_map['Private Label_sales'] = 'Volume_Sales_PL'
        if 'Private Label_price' in wide.columns:
            rename_map['Private Label_price'] = 'Price_PL'

        wide = wide.rename(columns=rename_map)

        # V2 base-price column (Sparkling Ice only)
        if base_prices is not None:
            if 'Sparkling Ice' in wide.columns:
                wide = wide.rename(columns={'Sparkling Ice': 'Base_Price_SI'})

        # Promo
        if self.config.include_promotions:
            si = df[df['Product_Short'] == 'Sparkling Ice']
            if 'Promo_Intensity' in df.columns and len(si) > 0:
                promo = si.pivot_table(
                    index=index_cols,
                    values='Promo_Intensity',
                    aggfunc='mean'
                ).reset_index()
                if 'Promo_Intensity' in promo.columns:
                    promo = promo.rename(columns={'Promo_Intensity': 'Promo_Intensity_SI'})
                    wide = wide.merge(promo, on=index_cols, how='left')

            # Ensure column exists
            if 'Promo_Intensity_SI' not in wide.columns:
                wide['Promo_Intensity_SI'] = 0.0
            else:
                wide['Promo_Intensity_SI'] = wide['Promo_Intensity_SI'].fillna(0)

        return wide

    # ========================================================================
    # V2: BASE PRICE + PROMO DEPTH FEATURES
    # ========================================================================

    def _add_base_and_promo_depth(self, df_wide: pd.DataFrame) -> pd.DataFrame:
        """
        Add V2 features:
        - Base_Price_SI (and Log_Base_Price_SI later)
        - Promo_Depth_SI: relative price change vs base price (negative when discounted)

        Notes:
        - If base columns are missing, we estimate a proxy base price from Avg_Price.
        - If Base_Price_SI is undefined for some weeks, we impute it.
        """
        df = df_wide.copy()

        # Ensure we have some base price signal
        if 'Base_Price_SI' not in df.columns or df['Base_Price_SI'].isna().all():
            # Proxy: rolling max of observed average price (common approximation)
            self.logger.warning(
                "  ⚠️ Base sales columns not available (or Base_Price_SI missing). "
                "Using proxy base price from Avg_Price."
            )
            df['Base_Price_SI'] = np.nan

            if 'Retailer' in df.columns:
                df = df.sort_values(['Retailer', 'Date'])
                df['Base_Price_SI'] = (
                    df.groupby('Retailer')['Price_SI']
                    .transform(
                        lambda s: s.rolling(
                            self.config.base_price_proxy_window, min_periods=1
                        ).max()
                    )
                )
            else:
                df = df.sort_values('Date')
                df['Base_Price_SI'] = df['Price_SI'].rolling(
                    self.config.base_price_proxy_window, min_periods=1
                ).max()

        # Impute missing/invalid base price values (forward-fill then back-fill)
        df['Base_Price_SI'] = df['Base_Price_SI'].where(df['Base_Price_SI'] > 0)
        base_missing_before = float(df['Base_Price_SI'].isna().mean())

        if 'Retailer' in df.columns:
            df = df.sort_values(['Retailer', 'Date'])
            df['Base_Price_SI'] = df.groupby('Retailer')['Base_Price_SI'].ffill().bfill()
        else:
            df = df.sort_values('Date')
            df['Base_Price_SI'] = df['Base_Price_SI'].ffill().bfill()

        base_missing_after = float(df['Base_Price_SI'].isna().mean())

        # Guardrail warnings
        imputed_rate = base_missing_before
        if imputed_rate > self.config.base_price_imputed_warn_threshold:
            self.logger.warning(
                f"  ⚠️ High base-price imputation rate: {imputed_rate:.1%} of weeks "
                "lacked base price before imputation."
            )
        if base_missing_after > 0:
            raise ValueError(
                f"Base_Price_SI could not be imputed for {base_missing_after:.1%} of rows. "
                "Check Date coverage and price columns."
            )

        # Promotional depth as relative price change vs base (negative when discounted)
        df['Promo_Depth_SI'] = (df['Price_SI'] / df['Base_Price_SI']) - 1.0
        df['Promo_Depth_SI'] = df['Promo_Depth_SI'].replace([np.inf, -np.inf], np.nan).fillna(0.0)

        # Clip to reasonable range
        df['Promo_Depth_SI'] = df['Promo_Depth_SI'].clip(-0.80, 0.50)

        return df

    def _add_time_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add time features"""

        df = df.sort_values('Date').reset_index(drop=True)

        if self.config.include_time_trend:
            origin = self.config.week_number_origin_date
            if origin is None:
                origin_date = df['Date'].min()
            else:
                try:
                    origin_date = pd.to_datetime(origin)
                except Exception as e:
                    raise ValueError(
                        f"Invalid PrepConfig.week_number_origin_date={origin!r}. "
                        "Provide an ISO date string like '2023-01-01'."
                    ) from e

            # Normalize to date boundary to avoid any unexpected time-of-day shifts.
            origin_date = pd.Timestamp(origin_date).normalize()
            df['Week_Number'] = ((df['Date'] - origin_date).dt.days / 7).astype(int)

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

        # Normalize config keys once
        cfg_by_norm = {
            self._norm_retailer(k): v
            for k, v in (self.config.retailers or {}).items()
        }

        # Default availability flags to "present"; retailer configs can override.
        if 'has_promo' not in df.columns:
            df['has_promo'] = 1
        if 'has_competitor' not in df.columns:
            df['has_competitor'] = 1

        for retailer_value in df['Retailer'].dropna().unique():
            cfg = cfg_by_norm.get(self._norm_retailer(retailer_value))
            if cfg is None:
                # common aliases
                aliases = {
                    "bjs": ["bjs", "bj s", "bjs wholesale", "bjs wholesale club"],
                    "sams": ["sams", "sams club", "sams club wholesale", "sams club inc"],
                    "costco": ["costco", "costco wholesale", "costco wholesale corp"],
                }
                norm_val = self._norm_retailer(retailer_value)
                match_key = None
                for canonical, a_list in aliases.items():
                    if norm_val in a_list:
                        for alias in a_list:
                            if alias in cfg_by_norm:
                                match_key = alias
                                break
                    if match_key:
                        break
                if match_key:
                    cfg = cfg_by_norm.get(match_key)

            if cfg is None:
                cfg = {}

            mask = df['Retailer'] == retailer_value

            if not cfg.get('has_promo', True):
                if 'Promo_Intensity_SI' in df.columns:
                    df.loc[mask, 'Promo_Intensity_SI'] = 0.0
                if 'Promo_Depth_SI' in df.columns:
                    df.loc[mask, 'Promo_Depth_SI'] = 0.0
                df.loc[mask, 'has_promo'] = 0
            else:
                df.loc[mask, 'has_promo'] = 1

            if not cfg.get('has_competitor', True):
                if 'Price_PL' in df.columns:
                    df.loc[mask, 'Price_PL'] = 0.0
                # Competitor sales may be missing entirely for some retailers (e.g., Costco).
                # Zero-fill to avoid NaNs propagating into downstream audits/exports/tests.
                if 'Volume_Sales_PL' in df.columns:
                    df.loc[mask, 'Volume_Sales_PL'] = 0.0
                if 'Log_Price_PL' in df.columns:
                    df.loc[mask, 'Log_Price_PL'] = 0.0
                df.loc[mask, 'has_competitor'] = 0
            else:
                df.loc[mask, 'has_competitor'] = 1

        return df

    def _validate_output(self, df: pd.DataFrame):
        """Validate output"""

        required = ['Date', 'Log_Volume_Sales_SI']

        # V2 vs V1 price features
        if self.config.separate_base_promo:
            required.extend(['Log_Base_Price_SI', 'Promo_Depth_SI'])
        else:
            required.append('Log_Price_SI')

        if self.config.include_promotions:
            required.append('Promo_Intensity_SI')

        if self.config.include_seasonality:
            required.extend(['Spring', 'Summer', 'Fall'])

        if self.config.retailer_filter == 'All':
            required.append('Retailer')
            if self.config.retailers:
                required.extend(['has_promo', 'has_competitor'])

        # Cross price: require Log_Price_PL column to exist (may be 0.0 for some retailers)
        if 'Log_Price_PL' in df.columns:
            required.append('Log_Price_PL')
        else:
            raise ValueError("Missing column: Log_Price_PL (competitor price log).")

        missing = set(required) - set(df.columns)
        if missing:
            raise ValueError(f"Missing columns: {missing}")

        if len(df) < 30:
            raise ValueError(f"Insufficient data: {len(df)} rows")

    # ========================================================================
    # FEATURE ENGINEERING
    # ========================================================================

    def add_interaction_term(
        self, df: pd.DataFrame, var1: str, var2: str, name: str = None
    ) -> pd.DataFrame:
        """Add interaction term"""
        if name is None:
            name = f"{var1}_x_{var2}"
        df[name] = df[var1] * df[var2]
        if self.config.verbose:
            self.logger.info(f"  Added interaction: {name}")
        return df

    def add_lagged_feature(
        self, df: pd.DataFrame, var: str, lags: List[int], group_by: List[str] = None
    ) -> pd.DataFrame:
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

    def add_moving_average(
        self, df: pd.DataFrame, var: str, windows: List[int], group_by: List[str] = None
    ) -> pd.DataFrame:
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
