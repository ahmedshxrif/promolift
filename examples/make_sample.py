"""Write examples/sales.csv: 26 weeks of made-up sales for six products with known elasticities.

Because the true elasticities are known, the tests can check that the fit recovers them.
"""

import csv
import math
import random
from pathlib import Path

# product, regular price, weekly units at that price, true elasticity
PRODUCTS = [
    ("fridge-family-650", 2899, 40, -5.5),
    ("fridge-compact-300", 1299, 55, -4.2),
    ("washer-front-9kg", 1799, 60, -3.6),
    ("washer-top-12kg", 1499, 35, -2.0),
    ("dryer-heat-pump", 2499, 18, -0.6),
    ("ac-split-1.5t", 1999, 70, -0.9),
]
DISCOUNTS = [0, 0, 0.05, 0, 0.1, 0, 0.15, 0.05, 0, 0.2, 0, 0.1, 0.25]


def main() -> None:
    random.seed(7)
    rows = []
    for sku, price, units, elasticity in PRODUCTS:
        for week in range(1, 27):
            discount = DISCOUNTS[(week + len(sku)) % len(DISCOUNTS)]
            noise = math.exp(random.gauss(0, 0.06))
            sold = units * (1 - discount) ** elasticity * noise
            rows.append({"sku": sku, "week": week, "price": round(price * (1 - discount)), "units": round(sold)})
    path = Path(__file__).with_name("sales.csv")
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["sku", "week", "price", "units"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows to {path}")


if __name__ == "__main__":
    main()
