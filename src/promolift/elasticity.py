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
    return Elasticity(sku, slope, max(0.0, r_squared), n, base_price, base_units)


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
