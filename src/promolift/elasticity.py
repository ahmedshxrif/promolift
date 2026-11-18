"""Estimate price elasticity from sales history.

Elasticity answers one question: when the price drops by 1%, by how many percent do sales rise?
An elasticity of -3 means a 1% cut sells about 3% more. Anything between 0 and -1 is "inelastic":
the product sells at roughly the same rate whatever the price, so discounting it gives money away.

The estimate is an ordinary least squares fit of log(units) against log(price). It is written out
by hand so the package needs nothing beyond the standard library, and so the arithmetic is readable.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


# Two-sided 95% critical values of Student's t, for 1 to 30 degrees of freedom.
_T95 = [
    12.706, 4.303, 3.182, 2.776, 2.571, 2.447, 2.365, 2.306, 2.262, 2.228,
    2.201, 2.179, 2.160, 2.145, 2.131, 2.120, 2.110, 2.101, 2.093, 2.086,
    2.080, 2.074, 2.069, 2.064, 2.060, 2.056, 2.052, 2.048, 2.045, 2.042,
]


def t_critical(degrees: int) -> float:
    """The multiplier for a 95% range. Few weeks means a wider range, so the table matters."""
    if degrees < 1:
        raise ValueError("need at least 1 degree of freedom")
    if degrees <= len(_T95):
        return _T95[degrees - 1]
    z = 1.959964  # beyond the table, the usual series around the normal value is accurate enough
    return z + (z**3 + z) / (4 * degrees) + (5 * z**5 + 16 * z**3 + 3 * z) / (96 * degrees**2)


@dataclass(frozen=True)
class Elasticity:
    sku: str
    elasticity: float
    """Percent change in units for a 1% change in price. Normally negative."""
    r_squared: float
    """How much of the movement in sales the price explains, from 0 to 1."""
    observations: int
    base_price: float
    """The highest price seen, taken as the regular price."""
    base_units: float
    """Typical weekly units at the regular price, read off the fitted line."""
    std_error: float = 0.0
    """Standard error of the elasticity: how far it would wander with another set of weeks."""
    low: float = 0.0
    """Lower end of the 95% range for the elasticity."""
    high: float = 0.0
    """Upper end of the 95% range for the elasticity."""

    @property
    def reliable(self) -> bool:
        """A fit worth acting on: enough weeks, and the price explains a fair share of the sales."""
        return self.observations >= 8 and self.r_squared >= 0.5 and self.elasticity < 0


def fit_elasticity(sku: str, prices: Iterable[float], units: Iterable[float]) -> Elasticity:
    """Fit one product. `prices` and `units` are matching weekly observations."""
    points = [(p, u) for p, u in zip(prices, units) if p > 0 and u > 0]
    if len(points) < 3:
        raise ValueError(f"{sku}: need at least 3 weeks with sales, got {len(points)}")
    xs = [math.log(p) for p, _ in points]
    ys = [math.log(u) for _, u in points]
    n = len(points)
    mean_x, mean_y = sum(xs) / n, sum(ys) / n
    spread_x = sum((x - mean_x) ** 2 for x in xs)
    if spread_x < 1e-9:
        raise ValueError(f"{sku}: the price never changed, so elasticity cannot be measured")
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / spread_x
    intercept = mean_y - slope * mean_x
    total = sum((y - mean_y) ** 2 for y in ys)
    residual = sum((y - (intercept + slope * x)) ** 2 for x, y in zip(xs, ys))
    r_squared = 1 - residual / total if total > 1e-12 else 0.0
    base_price = max(p for p, _ in points)
    base_units = math.exp(intercept + slope * math.log(base_price))
    # Residual variance uses n - 2 because two numbers (slope and intercept) were fitted.
    std_error = math.sqrt(residual / (n - 2) / spread_x)
    half = t_critical(n - 2) * std_error
    return Elasticity(sku, slope, max(0.0, r_squared), n, base_price, base_units,
                      std_error, slope - half, slope + half)


def read_sales(path: str | Path) -> dict[str, tuple[list[float], list[float]]]:
    """Read a CSV with the columns sku, price and units (one row per product per week)."""
    by_sku: dict[str, tuple[list[float], list[float]]] = {}
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        missing = {"sku", "price", "units"} - {name.strip().lower() for name in (reader.fieldnames or [])}
        if missing:
            raise ValueError(f"{path}: missing column(s): {', '.join(sorted(missing))}")
        for row in reader:
            clean = {key.strip().lower(): (value or "").strip() for key, value in row.items() if key}
            if not clean.get("sku"):
                continue
            prices, units = by_sku.setdefault(clean["sku"], ([], []))
            prices.append(float(clean["price"]))
            units.append(float(clean["units"]))
    return by_sku


def fit_all(path: str | Path) -> tuple[list[Elasticity], list[str]]:
    """Fit every product in a sales file. Returns the fits, and a note for each product skipped."""
    fits: list[Elasticity] = []
    skipped: list[str] = []
    for sku, (prices, units) in read_sales(path).items():
        try:
            fits.append(fit_elasticity(sku, prices, units))
        except ValueError as problem:
            skipped.append(str(problem))
    return sorted(fits, key=lambda fit: fit.elasticity), skipped
