# promolift

[![tests](https://github.com/ahmedshxrif/promolift/actions/workflows/ci.yml/badge.svg)](https://github.com/ahmedshxrif/promolift/actions/workflows/ci.yml)
![python](https://img.shields.io/badge/python-3.10%2B-3776ab)
![dependencies](https://img.shields.io/badge/dependencies-none-success)
![license](https://img.shields.io/badge/license-MIT-blue)

**Find where a discount pays for itself.** Give promolift your sales history and it tells you how sensitive each product is to price, the discount at which its profit peaks, and how to spend a promo budget so it earns the most.

```
$ promolift plan examples/sales.csv --budget 20000

product             discount  spend   extra units  extra profit
------------------  --------  ------  -----------  ------------
fridge-family-650   9%        17,426  +27          +5,974
fridge-compact-300  3%        2,403   +8           +617
ac-split-1.5t       0%        0       +0           +0
washer-front-9kg    0%        0       +0           +0
washer-top-12kg     0%        0       +0           +0
dryer-heat-pump     0%        0       +0           +0

Budget used:              19,829 of 20,000 a week
Extra profit:             +6,590 a week
Same budget, even split:  -2,673 a week
Gain from targeting:      +9,263 a week
```

Read the last three lines. The same 20,000 a week **loses** money when every product gets the same discount, and **makes** money when it goes only to the products that repay it.

## The idea

Promo budgets are often spread evenly, or handed to whichever product had a promotion last year. But products react to price very differently:

- Some are **elastic**: cut the price a little and sales jump. A discount there can pay for itself.
- Some are **inelastic**: they sell at about the same rate whatever the price. A discount there just gives margin away.

promolift measures which is which from your own sales, then does the arithmetic.

## Install

```bash
pip install git+https://github.com/ahmedshxrif/promolift
```

It has no dependencies beyond Python 3.10.

## Use it

Your data is a CSV with one row per product per week:

```csv
sku,week,price,units
fridge-family-650,1,2899,41
fridge-family-650,2,2609,72
```

**Step 1: measure.**

```
$ promolift fit examples/sales.csv

product             elasticity (95% range)  fit   weeks  best discount  reliable
------------------  ----------------------  ----  -----  -------------  --------
fridge-family-650   -5.47 (-5.7 to -5.2)    0.99  26     14%            yes
fridge-compact-300  -4.41 (-4.6 to -4.2)    0.99  26     9%             yes
washer-front-9kg    -3.44 (-3.7 to -3.1)    0.96  26     1%             yes
washer-top-12kg     -2.13 (-2.4 to -1.9)    0.92  26     0%             yes
ac-split-1.5t       -0.77 (-1.0 to -0.5)    0.61  26     0%             yes
dryer-heat-pump     -0.66 (-0.9 to -0.5)    0.66  26     0%             yes
```

| Column | Meaning |
|---|---|
| elasticity | Percent change in sales for a 1% change in price. -5.47 means a 1% cut sells about 5.5% more |
| 95% range | Where the true elasticity most likely lies. A wide range means the data is thin or noisy. Also on the `Elasticity` object as `low`, `high` and `std_error` |
| fit | How much of the movement in sales the price explains, from 0 to 1 |
| best discount | The discount at which profit peaks, at your margin |
| reliable | At least 8 weeks of data, a fit of 0.5 or better, and a negative elasticity |

**Step 2: plan.** `promolift plan sales.csv --budget 20000` gives the table at the top. Options: `--margin 0.3` (share of the price that is profit) and `--max-discount 0.4`.

**Step 3: export.** Both commands take `--format text|markdown|json`. Text is the default. Warnings still go to stderr, so the output on stdout stays clean.

Markdown, for a report:

```
$ promolift fit examples/sales.csv --format markdown

| product | elasticity (95% range) | fit | weeks | best discount | reliable |
| --- | --- | --- | --- | --- | --- |
| fridge-family-650 | -5.47 (-5.7 to -5.2) | 0.99 | 26 | 14% | yes |
```

JSON, for another tool (numbers are unrounded):

```
$ promolift plan examples/sales.csv --budget 20000 --format json

{"lines": [{"sku": "fridge-family-650", "discount": 0.09, ...}], "budget": 20000.0, "spend": ..., "extra_profit": ..., "even_split_profit": ..., "gain_over_even_split": ...}
```

**Or from Python:**

```python
from promolift import fit_all, plan_budget

fits, skipped = fit_all("sales.csv")
plan = plan_budget([f for f in fits if f.reliable], budget=20_000, margin=0.3)

for line in plan.lines:
    print(line.sku, f"{line.discount:.0%}", round(line.extra_profit))
```

## How it works

**Measuring.** For each product, promolift fits a straight line through log(units) against log(price). The slope of that line is the elasticity. The fit is written out by hand in about twenty lines, so you can read exactly what it does.

**Finding the best discount.** At a discount `d`, sales multiply by `(1 - d) ** elasticity`, and profit per unit shrinks by the discount. Profit peaks where those two effects balance. One consequence is worth knowing: with a 30% margin, a discount only pays when elasticity is beyond about -3.3. Below that, every cut loses money, however good the sales bump looks.

**Spending the budget.** Start with no discounts. Give the next percentage point of discount to whichever product earns the most extra profit per unit of budget. Repeat until the budget is gone or nothing earns any more.

## Does the measurement work?

The sample data in `examples/` is generated from six products with known elasticities, plus random noise. The tests check that the fit recovers every one of them:

| Product | True | Measured |
|---|---|---|
| fridge-family-650 | -5.5 | -5.47 |
| fridge-compact-300 | -4.2 | -4.41 |
| washer-front-9kg | -3.6 | -3.44 |
| washer-top-12kg | -2.0 | -2.13 |
| ac-split-1.5t | -0.9 | -0.77 |
| dryer-heat-pump | -0.6 | -0.66 |

```bash
python -m unittest discover -s tests   # 27 tests
```

## Limits, plainly

- **It assumes the price is what moved sales.** A holiday week, a stock-out or a competitor's promotion will all bend the estimate. Use more weeks, and look at the `fit` column.
- **One product at a time.** It doesn't model one product's discount stealing sales from another.
- **Constant elasticity.** Real products stop responding at some point. Keep `--max-discount` sensible.
- **Short-term only.** It measures the sales bump during the promotion, not what happens to sales the week after.

It is a tool for a first, honest answer to "where should the promo money go?", not a replacement for a pricing team.

## Where it came from

I built a model like this at work to help decide where a promotional budget should go. This is a clean rebuild of that idea with made-up data.

## License

MIT
