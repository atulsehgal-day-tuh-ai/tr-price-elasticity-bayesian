"""
Command-Line Interface for Price Elasticity Analysis

Complete end-to-end pipeline for Bayesian price elasticity analysis.

Usage:
    # Basic usage
    python run_analysis.py --bjs data/bjs.csv --sams data/sams.csv --output ./results
    
    # With configuration file
    python run_analysis.py --config config.yaml
    
    # Hierarchical model
    python run_analysis.py --bjs data/bjs.csv --sams data/sams.csv --hierarchical --output ./results
    
    # With Costco
    python run_analysis.py --bjs data/bjs.csv --sams data/sams.csv --costco data/costco.csv --hierarchical
"""

import argparse
import yaml
import sys
from pathlib import Path
import logging
from datetime import datetime

# Import our modules
from data_prep import ElasticityDataPrep, PrepConfig
from bayesian_models import SimpleBayesianModel, HierarchicalBayesianModel
from visualizations import generate_html_report


# ============================================================================
# LOGGING SETUP
# ============================================================================

def setup_logging(output_dir: Path, verbose: bool = True):
    """Setup logging to file and console"""
    
    log_file = output_dir / 'analysis.log'
    
    # Create logger
    logger = logging.getLogger('PriceElasticityAnalysis')
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    
    # File handler
    fh = logging.FileHandler(log_file)
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    
    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO if verbose else logging.WARNING)
    ch.setFormatter(logging.Formatter('%(message)s'))
    
    logger.addHandler(fh)
    logger.addHandler(ch)
    
    return logger


# ============================================================================
# CONFIG HELPERS (backwards compatible)
# ============================================================================

def _get_verbose_flag(config: dict, default: bool = True) -> bool:
    """Return verbose flag from config, supporting both `logging.verbose` and legacy `advanced.verbose`."""
    if not isinstance(config, dict):
        return default
    if isinstance(config.get('logging'), dict) and 'verbose' in config['logging']:
        return bool(config['logging']['verbose'])
    if isinstance(config.get('advanced'), dict) and 'verbose' in config['advanced']:
        return bool(config['advanced']['verbose'])
    return default


def _get_output_dir(config: dict, default: str = './output') -> str:
    """Return output directory from config, supporting both `output.output_dir` and legacy `output.directory`."""
    if not isinstance(config, dict):
        return default
    output = config.get('output', {})
    if isinstance(output, dict):
        return output.get('output_dir') or output.get('directory') or default
    return default


# ============================================================================
# CONFIGURATION LOADING
# ============================================================================

def load_config(config_path: str) -> dict:
    """Load configuration from YAML file"""
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    return config


def parse_arguments():
    """Parse command-line arguments"""
    
    parser = argparse.ArgumentParser(
        description='Bayesian Price Elasticity Analysis Pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic analysis
  python run_analysis.py --bjs data/bjs.csv --sams data/sams.csv --output ./results
  
  # Hierarchical model
  python run_analysis.py --bjs data/bjs.csv --sams data/sams.csv --hierarchical
  
  # With configuration file
  python run_analysis.py --config config.yaml
  
  # With Costco data
  python run_analysis.py --bjs data/bjs.csv --sams data/sams.csv --costco data/costco.csv --hierarchical
        """
    )
    
    # Input files
    parser.add_argument('--bjs', type=str, help='Path to BJ\'s CSV file')
    parser.add_argument('--sams', type=str, help='Path to Sam\'s Club CSV file')
    parser.add_argument('--costco', type=str, help='Path to Costco CSV file (optional)')
    
    # Configuration
    parser.add_argument('--config', type=str, help='Path to YAML configuration file')
    
    # Model options
    parser.add_argument('--hierarchical', action='store_true', 
                       help='Use hierarchical model (default: simple)')
    parser.add_argument('--priors', type=str, default='default',
                       choices=['default', 'informative', 'vague'],
                       help='Prior specification (default: default)')
    
    # MCMC options
    parser.add_argument('--samples', type=int, default=2000,
                       help='Number of MCMC samples (default: 2000)')
    parser.add_argument('--chains', type=int, default=4,
                       help='Number of MCMC chains (default: 4)')
    parser.add_argument('--tune', type=int, default=1000,
                       help='Number of tuning steps (default: 1000)')
    
    # Data options
    parser.add_argument('--retailer-filter', type=str, default='All',
                       choices=['Overall', 'All', 'BJs', 'Sams', 'Costco'],
                       help='Retailer filter (default: All)')
    
    # Output options
    parser.add_argument('--output', type=str, default='./output',
                       help='Output directory (default: ./output)')
    parser.add_argument('--no-plots', action='store_true',
                       help='Skip plot generation')
    parser.add_argument('--no-html', action='store_true',
                       help='Skip HTML report generation')
    
    # Other
    parser.add_argument('--seed', type=int, default=42,
                       help='Random seed (default: 42)')
    parser.add_argument('--verbose', action='store_true',
                       help='Verbose output')
    
    return parser.parse_args()


# ============================================================================
# MAIN PIPELINE
# ============================================================================

def run_pipeline(config: dict, logger):
    """
    Main analysis pipeline
    
    Steps:
    1. Data preparation
    2. Model fitting
    3. Results generation
    4. Visualization
    5. HTML report
    """
    
    logger.info("="*80)
    logger.info("STARTING BAYESIAN PRICE ELASTICITY ANALYSIS")
    logger.info("="*80)
    logger.info(f"\nTimestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Create output directory
    output_dir = Path(_get_output_dir(config))
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Output directory: {output_dir}")
    
    # ========================================================================
    # STEP 1: DATA PREPARATION
    # ========================================================================
    
    logger.info("\n" + "="*80)
    logger.info("STEP 1: DATA PREPARATION")
    logger.info("="*80)
    
    # Create prep config
    prep_config = PrepConfig(
        retailer_filter=config['data']['retailer_filter'],
        include_seasonality=config['data']['include_seasonality'],
        include_promotions=config['data']['include_promotions'],
        include_time_trend=config['data']['include_time_trend'],
        log_transform_sales=config['data']['log_transform_sales'],
        log_transform_prices=config['data']['log_transform_prices'],
        retailers=config['data'].get('retailers'),
        verbose=_get_verbose_flag(config, default=True)
    )
    
    # Initialize prep
    prep = ElasticityDataPrep(prep_config)
    
    # Transform data
    data = prep.transform(
        bjs_path=config['data']['bjs_path'],
        sams_path=config['data']['sams_path'],
        costco_path=config['data'].get('costco_path')
    )
    
    logger.info(f"\n✓ Data preparation complete")
    logger.info(f"  Final shape: {data.shape}")
    logger.info(f"  Date range: {data['Date'].min()} to {data['Date'].max()}")
    
    # Save prepared data
    data_path = output_dir / 'prepared_data.csv'
    data.to_csv(data_path, index=False)
    logger.info(f"  Saved to: {data_path}")
    
    # ========================================================================
    # STEP 2: MODEL FITTING
    # ========================================================================
    
    logger.info("\n" + "="*80)
    logger.info("STEP 2: BAYESIAN MODEL FITTING")
    logger.info("="*80)
    
    model_type = config['model']['type']
    logger.info(f"\nModel type: {model_type}")
    logger.info(f"Prior specification: {config['model']['priors']}")
    logger.info(f"MCMC settings: {config['model']['n_samples']} samples × {config['model']['n_chains']} chains")
    
    # Create model
    if model_type == 'hierarchical':
        model = HierarchicalBayesianModel(
            priors=config['model']['priors'],
            n_samples=config['model']['n_samples'],
            n_tune=config['model']['n_tune'],
            n_chains=config['model']['n_chains'],
            target_accept=config['model']['target_accept'],
            random_seed=config['model']['random_seed'],
            verbose=config.get('logging', {}).get('verbose', True)
        )
    else:
        model = SimpleBayesianModel(
            priors=config['model']['priors'],
            n_samples=config['model']['n_samples'],
            n_tune=config['model']['n_tune'],
            n_chains=config['model']['n_chains'],
            target_accept=config['model']['target_accept'],
            random_seed=config['model']['random_seed'],
            verbose=config.get('logging', {}).get('verbose', True)
        )
    
    # Fit model
    results = model.fit(data)
    
    logger.info(f"\n✓ Model fitting complete")
    logger.info(f"  Convergence: {'✓ Passed' if results.converged else '⚠️ Warnings'}")
    logger.info(f"  Max R-hat: {results.rhat_max:.4f}")
    logger.info(f"  Min ESS: {results.ess_min:.0f}")
    
    # ========================================================================
    # STEP 3: SAVE RESULTS
    # ========================================================================
    
    logger.info("\n" + "="*80)
    logger.info("STEP 3: SAVING RESULTS")
    logger.info("="*80)
    
    # Save summary
    if config['output']['save_summary']:
        summary_path = output_dir / 'model_summary.txt'
        with open(summary_path, 'w') as f:
            f.write(results.summary())
        logger.info(f"\n✓ Summary saved to: {summary_path}")
    
    # Save trace (optional)
    if config['output']['save_trace']:
        import arviz as az
        trace_path = output_dir / 'trace.nc'
        results.trace.to_netcdf(trace_path)
        logger.info(f"✓ Trace saved to: {trace_path}")
    
    # Create results table
    results_data = {
        'Parameter': ['Own-Price Elasticity', 'Cross-Price Elasticity', 'Promotional Effect'],
        'Mean': [
            results.elasticity_own.mean,
            results.elasticity_cross.mean if results.elasticity_cross else None,
            results.beta_promo.mean if results.beta_promo else None
        ],
        'CI_Lower': [
            results.elasticity_own.ci_lower,
            results.elasticity_cross.ci_lower if results.elasticity_cross else None,
            results.beta_promo.ci_lower if results.beta_promo else None
        ],
        'CI_Upper': [
            results.elasticity_own.ci_upper,
            results.elasticity_cross.ci_upper if results.elasticity_cross else None,
            results.beta_promo.ci_upper if results.beta_promo else None
        ]
    }
    
    import pandas as pd
    results_df = pd.DataFrame(results_data)
    results_csv = output_dir / 'results_summary.csv'
    results_df.to_csv(results_csv, index=False)
    logger.info(f"✓ Results table saved to: {results_csv}")
    
    # ========================================================================
    # STEP 4: GENERATE VISUALIZATIONS
    # ========================================================================
    
    if config['output']['generate_plots']:
        logger.info("\n" + "="*80)
        logger.info("STEP 4: GENERATING VISUALIZATIONS")
        logger.info("="*80)
        
        from visualizations import create_all_plots
        
        plots_dir = output_dir / 'plots'
        create_all_plots(results, data, output_dir=str(plots_dir))
        
        logger.info(f"\n✓ All plots saved to: {plots_dir}")
    
    # ========================================================================
    # STEP 5: GENERATE HTML REPORT
    # ========================================================================
    
    if config['output']['generate_html']:
        logger.info("\n" + "="*80)
        logger.info("STEP 5: GENERATING HTML REPORT")
        logger.info("="*80)
        
        report_path = generate_html_report(
            results=results,
            data=data,
            output_dir=str(output_dir),
            report_name='elasticity_report.html'
        )
        
        logger.info(f"\n✓ HTML report generated: {report_path}")
    
    # ========================================================================
    # FINAL SUMMARY
    # ========================================================================
    
    logger.info("\n" + "="*80)
    logger.info("✓ ANALYSIS COMPLETE")
    logger.info("="*80)
    
    logger.info(f"\n📊 KEY RESULTS:")
    logger.info(f"  Own-Price Elasticity: {results.elasticity_own.mean:.3f} [{results.elasticity_own.ci_lower:.3f}, {results.elasticity_own.ci_upper:.3f}]")
    
    if results.elasticity_cross:
        logger.info(f"  Cross-Price Elasticity: {results.elasticity_cross.mean:.3f} [{results.elasticity_cross.ci_lower:.3f}, {results.elasticity_cross.ci_upper:.3f}]")
    
    if abs(results.elasticity_own.mean) > 1:
        logger.info(f"\n  → Demand is ELASTIC (price increases hurt revenue)")
    else:
        logger.info(f"\n  → Demand is INELASTIC (price increases boost revenue)")
    
    logger.info(f"\n📁 OUTPUT FILES:")
    logger.info(f"  Directory: {output_dir}")
    logger.info(f"  - prepared_data.csv")
    logger.info(f"  - model_summary.txt")
    logger.info(f"  - results_summary.csv")
    if config['output']['generate_plots']:
        logger.info(f"  - plots/ (all diagnostic plots)")
    if config['output']['generate_html']:
        logger.info(f"  - elasticity_report.html")
    logger.info(f"  - analysis.log")
    
    logger.info(f"\n💡 NEXT STEPS:")
    logger.info(f"  1. Review HTML report: {output_dir}/elasticity_report.html")
    logger.info(f"  2. Check convergence in model_summary.txt")
    logger.info(f"  3. Use results_summary.csv for further analysis")
    
    return results


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """Main entry point"""
    
    # Parse arguments
    args = parse_arguments()
    
    # Load or create configuration
    if args.config:
        # Load from config file
        config = load_config(args.config)
    else:
        # Create from command-line arguments
        if not args.bjs or not args.sams:
            print("Error: --bjs and --sams are required (or use --config)")
            sys.exit(1)
        
        config = {
            'data': {
                'bjs_path': args.bjs,
                'sams_path': args.sams,
                'costco_path': args.costco,
                'retailer_filter': 'All' if args.hierarchical else args.retailer_filter,
                'include_seasonality': True,
                'include_promotions': True,
                'include_time_trend': True,
                'log_transform_sales': True,
                'log_transform_prices': True,
                'retailers': None
            },
            'model': {
                'type': 'hierarchical' if args.hierarchical else 'simple',
                'priors': args.priors,
                'n_samples': args.samples,
                'n_tune': args.tune,
                'n_chains': args.chains,
                'target_accept': 0.95,
                'max_rhat': 1.01,
                'min_ess': 400,
                'random_seed': args.seed
            },
            'output': {
                'output_dir': args.output,
                'generate_plots': not args.no_plots,
                'generate_html': not args.no_html,
                'save_trace': True,
                'save_summary': True,
                'credible_interval': 0.95
            },
            'logging': {
                'verbose': args.verbose,
                'log_to_file': True
            }
        }
    
    # Setup logging
    output_dir = Path(_get_output_dir(config))
    output_dir.mkdir(parents=True, exist_ok=True)
    logger = setup_logging(output_dir, verbose=_get_verbose_flag(config, default=True))
    
    # Run pipeline
    try:
        results = run_pipeline(config, logger)
        logger.info("\n✓ Pipeline completed successfully!")
        return 0
        
    except Exception as e:
        logger.error(f"\n❌ Pipeline failed with error:")
        logger.error(f"  {str(e)}")
        logger.exception("Full traceback:")
        return 1


if __name__ == '__main__':
    sys.exit(main())
