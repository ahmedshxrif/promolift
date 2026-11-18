"""promolift: find where a discount pays for itself."""

from .elasticity import Elasticity, fit_elasticity, fit_all, read_sales, t_critical
from .plan import Line, Plan, best_discount, plan_budget, profit_change, units_multiplier

__all__ = [
    "Elasticity", "fit_elasticity", "fit_all", "read_sales", "t_critical",
    "Line", "Plan", "best_discount", "plan_budget", "profit_change", "units_multiplier",
]
__version__ = "0.1.0"
