"""Command line: `promolift fit sales.csv` and `promolift plan sales.csv --budget 5000`."""

from __future__ import annotations

import argparse
import sys

from .elasticity import fit_all
from .plan import best_discount, plan_budget


def _table(headers: list[str], rows: list[list[str]]) -> str:
    widths = [max(len(str(cell)) for cell in column) for column in zip(headers, *rows)]
    line = lambda cells: "  ".join(str(cell).ljust(width) for cell, width in zip(cells, widths)).rstrip()
    return "\n".join([line(headers), line(["-" * width for width in widths]), *(line(row) for row in rows)])


def _fit(args: argparse.Namespace) -> int:
    fits, skipped = fit_all(args.sales)
    rows = [
        [fit.sku, f"{fit.elasticity:.2f}", f"{fit.r_squared:.2f}", str(fit.observations),
         f"{best_discount(fit.elasticity, args.margin):.0%}",
         "yes" if fit.reliable else "check"]
        for fit in fits
    ]
    print(_table(["product", "elasticity", "fit", "weeks", "best discount", "reliable"], rows))
    for note in skipped:
        print(f"skipped: {note}", file=sys.stderr)
    return 0


def _plan(args: argparse.Namespace) -> int:
    fits, skipped = fit_all(args.sales)
    usable = [fit for fit in fits if fit.reliable]
    for fit in fits:
        if not fit.reliable:
            print(f"left out: {fit.sku} (the fit is too weak to act on)", file=sys.stderr)
    for note in skipped:
        print(f"skipped: {note}", file=sys.stderr)
    if not usable:
        print("No product has a fit reliable enough to plan with.", file=sys.stderr)
        return 1
    plan = plan_budget(usable, args.budget, args.margin, args.max_discount)
    rows = [
        [line.sku, f"{line.discount:.0%}", f"{line.spend:,.0f}", f"{line.extra_units:+,.0f}", f"{line.extra_profit:+,.0f}"]
        for line in plan.lines
    ]
    print(_table(["product", "discount", "spend", "extra units", "extra profit"], rows))
    print()
    print(f"Budget used:              {plan.spend:,.0f} of {plan.budget:,.0f} a week")
    print(f"Extra profit:             {plan.extra_profit:+,.0f} a week")
    print(f"Same budget, even split:  {plan.even_split_profit:+,.0f} a week")
    print(f"Gain from targeting:      {plan.gain_over_even_split:+,.0f} a week")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="promolift", description="Find where a discount pays for itself.")
    commands = parser.add_subparsers(dest="command", required=True)

    fit = commands.add_parser("fit", help="estimate price elasticity for every product in a sales file")
    fit.add_argument("sales", help="CSV with the columns sku, price, units")
    fit.add_argument("--margin", type=float, default=0.3, help="share of the regular price that is profit (default 0.3)")
    fit.set_defaults(run=_fit)

    plan = commands.add_parser("plan", help="spend a weekly promo budget where it earns the most")
    plan.add_argument("sales", help="CSV with the columns sku, price, units")
    plan.add_argument("--budget", type=float, required=True, help="discount money available per week")
    plan.add_argument("--margin", type=float, default=0.3, help="share of the regular price that is profit (default 0.3)")
    plan.add_argument("--max-discount", type=float, default=0.4, help="deepest discount allowed (default 0.4)")
    plan.set_defaults(run=_plan)

    args = parser.parse_args(argv)
    try:
        return args.run(args)
    except (OSError, ValueError) as problem:
        print(f"error: {problem}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
