"""Command line: `promolift fit sales.csv` and `promolift plan sales.csv --budget 5000`."""

from __future__ import annotations

import argparse
import json
import sys

from .elasticity import fit_all
from .plan import best_discount, plan_budget

FORMATS = ["text", "markdown", "json"]


def _table(headers: list[str], rows: list[list[str]]) -> str:
    widths = [max(len(str(cell)) for cell in column) for column in zip(headers, *rows)]
    line = lambda cells: "  ".join(str(cell).ljust(width) for cell, width in zip(cells, widths)).rstrip()
    return "\n".join([line(headers), line(["-" * width for width in widths]), *(line(row) for row in rows)])


def _markdown(headers: list[str], rows: list[list[str]]) -> str:
    line = lambda cells: "| " + " | ".join(str(cell) for cell in cells) + " |"
    return "\n".join([line(headers), line(["---"] * len(headers)), *(line(row) for row in rows)])


def _fit(args: argparse.Namespace) -> int:
    fits, skipped = fit_all(args.sales)
    for note in skipped:
        print(f"skipped: {note}", file=sys.stderr)
    if args.format == "json":
        records = [
            {"sku": fit.sku, "elasticity": fit.elasticity, "low": fit.low, "high": fit.high, "std_error": fit.std_error,
             "r_squared": fit.r_squared, "weeks": fit.observations,
             "best_discount": best_discount(fit.elasticity, args.margin), "reliable": fit.reliable}
            for fit in fits
        ]
        print(json.dumps({"products": records, "skipped": skipped}, indent=2))
        return 0
    rows = [
        [fit.sku, f"{fit.elasticity:.2f} ({fit.low:.1f} to {fit.high:.1f})", f"{fit.r_squared:.2f}", str(fit.observations),
         f"{best_discount(fit.elasticity, args.margin):.0%}",
         "yes" if fit.reliable else "check"]
        for fit in fits
    ]
    render = _markdown if args.format == "markdown" else _table
    print(render(["product", "elasticity (95% range)", "fit", "weeks", "best discount", "reliable"], rows))
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
    if args.format == "json":
        document = {
            "lines": [
                {"sku": l.sku, "discount": l.discount, "spend": l.spend, "extra_units": l.extra_units, "extra_profit": l.extra_profit}
                for l in plan.lines
            ],
            "budget": plan.budget, "spend": plan.spend, "extra_profit": plan.extra_profit,
            "even_split_profit": plan.even_split_profit, "gain_over_even_split": plan.gain_over_even_split,
        }
        print(json.dumps(document, indent=2))
        return 0
    rows = [
        [line.sku, f"{line.discount:.0%}", f"{line.spend:,.0f}", f"{line.extra_units:+,.0f}", f"{line.extra_profit:+,.0f}"]
        for line in plan.lines
    ]
    summary = [
        ("Budget used", f"{plan.spend:,.0f} of {plan.budget:,.0f} a week"),
        ("Extra profit", f"{plan.extra_profit:+,.0f} a week"),
        ("Same budget, even split", f"{plan.even_split_profit:+,.0f} a week"),
        ("Gain from targeting", f"{plan.gain_over_even_split:+,.0f} a week"),
    ]
    headers = ["product", "discount", "spend", "extra units", "extra profit"]
    if args.format == "markdown":
        print(_markdown(headers, rows))
        print()
        for name, value in summary:
            print(f"- **{name}:** {value}")
        return 0
    print(_table(headers, rows))
    print()
    for name, value in summary:
        print(f"{(name + ':').ljust(26)}{value}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="promolift", description="Find where a discount pays for itself.")
    commands = parser.add_subparsers(dest="command", required=True)

    fit = commands.add_parser("fit", help="estimate price elasticity for every product in a sales file")
    fit.add_argument("sales", help="CSV with the columns sku, price, units")
    fit.add_argument("--margin", type=float, default=0.3, help="share of the regular price that is profit (default 0.3)")
    fit.add_argument("--format", choices=FORMATS, default="text", help="text, markdown or json (default text)")
    fit.set_defaults(run=_fit)

    plan = commands.add_parser("plan", help="spend a weekly promo budget where it earns the most")
    plan.add_argument("sales", help="CSV with the columns sku, price, units")
    plan.add_argument("--budget", type=float, required=True, help="discount money available per week")
    plan.add_argument("--margin", type=float, default=0.3, help="share of the regular price that is profit (default 0.3)")
    plan.add_argument("--max-discount", type=float, default=0.4, help="deepest discount allowed (default 0.4)")
    plan.add_argument("--format", choices=FORMATS, default="text", help="text, markdown or json (default text)")
    plan.set_defaults(run=_plan)

    args = parser.parse_args(argv)
    try:
        return args.run(args)
    except (OSError, ValueError) as problem:
        print(f"error: {problem}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
