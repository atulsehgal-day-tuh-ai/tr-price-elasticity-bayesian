"""
Report generation package (contract-driven).

Exports two public entry points used by `visualizations.py` / `run_analysis.py`:
- generate_statistical_report
- generate_business_report
"""

from reporting.statistical_report import generate_statistical_report
from reporting.business_report import generate_business_report

