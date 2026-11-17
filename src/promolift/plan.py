"""Turn elasticities into a plan: which products to discount, by how much, within a budget.

The model is the standard constant-elasticity one: selling at a discount `d` multiplies units by
(1 - d) ** elasticity. Profit per unit is what is left of the price after the discount and the cost.
"""

from __future__ import annotations

from dataclasses import dataclass

from .elasticity import Elasticity

STEP = 0.01  # discounts are planned in whole percentage points


def units_multiplier(elasticity: float, discount: float) -> float:
    """How many times more units sell at this discount. 1.0 means no change."""
    return (1 - discount) ** elasticity


def profit_change(elasticity: float, margin: float, discount: float) -> float:
    """Profit at this discount compared with no discount, as a ratio. 0.25 means 25% more profit.

    `margin` is the share of the regular price that is profit, for example 0.3.
    """
    if not 0 < margin < 1:
        raise ValueError("margin must be between 0 and 1")
    cost = 1 - margin
    unit_profit = (1 - discount) - cost
    return units_multiplier(elasticity, discount) * unit_profit / margin - 1


def best_discount(elasticity: float, margin: float, max_discount: float = 0.4) -> float:
    """The discount at which profit peaks, rounded to a whole percent.

    A product whose elasticity is between 0 and -1 never repays a discount, so the answer is 0.
    """
    if elasticity >= -1:
        return 0.0
    cost = 1 - margin
    best_price_share = elasticity * cost / (elasticity + 1)  # where the profit curve is flat
    discount = min(max(1 - best_price_share, 0.0), max_discount)
    return round(discount / STEP) * STEP


@dataclass(frozen=True)
class Line:
    sku: str
    discount: float
    spend: float
    """Money given away as discount on the units sold."""
    extra_units: float
    extra_profit: float


@dataclass(frozen=True)
class Plan:
    lines: list[Line]
    budget: float
    spend: float
    extra_profit: float
    even_split_profit: float
    """What the same budget earns when every product gets the same discount."""

    @property
    def gain_over_even_split(self) -> float:
        return self.extra_profit - self.even_split_profit


def _figures(fit: Elasticity, margin: float, discount: float) -> tuple[float, float, float]:
    """Spend, extra units and extra profit for one product at one discount, per week."""
    units = fit.base_units * units_multiplier(fit.elasticity, discount)
    spend = discount * fit.base_price * units
    base_profit = fit.base_units * fit.base_price * margin
    extra_profit = base_profit * profit_change(fit.elasticity, margin, discount)
    return spend, units - fit.base_units, extra_profit


def _even_split(fits: list[Elasticity], margin: float, budget: float, max_discount: float) -> float:
    """Extra profit when one shared discount is chosen so that total spend just fits the budget."""
    low, high = 0.0, max_discount
    for _ in range(40):
        middle = (low + high) / 2
        if sum(_figures(fit, margin, middle)[0] for fit in fits) > budget:
            high = middle
        else:
            low = middle
    return sum(_figures(fit, margin, low)[2] for fit in fits)


def plan_budget(fits: list[Elasticity], budget: float, margin: float = 0.3, max_discount: float = 0.4) -> Plan:
    """Spend a weekly promo budget where it earns the most.

    Starting from no discount anywhere, give the next percentage point to whichever product earns
    the most extra profit per unit of budget, and stop when the budget runs out or when no further
    discount adds profit.
    """
    discounts = {fit.sku: 0.0 for fit in fits}
    spent = 0.0
    while True:
        best = None
        for fit in fits:
            now = discounts[fit.sku]
            if now + STEP > max_discount + 1e-9:
                continue
            spend_now, _, profit_now = _figures(fit, margin, now)
            spend_next, _, profit_next = _figures(fit, margin, now + STEP)
            extra_spend, extra_profit = spend_next - spend_now, profit_next - profit_now
            if extra_profit <= 0 or extra_spend <= 0 or spent + extra_spend > budget:
                continue
            rate = extra_profit / extra_spend
            if best is None or rate > best[0]:
                best = (rate, fit.sku, extra_spend)
        if best is None:
            break
        discounts[best[1]] = round(discounts[best[1]] + STEP, 2)
        spent += best[2]

    lines = []
    for fit in fits:
        spend, extra_units, extra_profit = _figures(fit, margin, discounts[fit.sku])
        lines.append(Line(fit.sku, discounts[fit.sku], spend, extra_units, extra_profit))
    lines.sort(key=lambda line: line.extra_profit, reverse=True)
    return Plan(
        lines=lines,
        budget=budget,
        spend=sum(line.spend for line in lines),
        extra_profit=sum(line.extra_profit for line in lines),
        even_split_profit=_even_split(fits, margin, budget, max_discount),
    )
