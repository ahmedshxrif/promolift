import math
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from promolift import best_discount, fit_all, fit_elasticity, plan_budget, profit_change, t_critical, units_multiplier  # noqa: E402

SALES = ROOT / "examples" / "sales.csv"
TRUE = {
    "fridge-family-650": -5.5, "fridge-compact-300": -4.2, "washer-front-9kg": -3.6,
    "washer-top-12kg": -2.0, "dryer-heat-pump": -0.6, "ac-split-1.5t": -0.9,
}


class Elasticity(unittest.TestCase):
    def test_exact_data_gives_the_exact_answer(self):
        prices = [100, 90, 80, 70, 60]
        units = [50 * (p / 100) ** -2.5 for p in prices]
        fit = fit_elasticity("x", prices, units)
        self.assertAlmostEqual(fit.elasticity, -2.5, places=6)
        self.assertAlmostEqual(fit.r_squared, 1.0, places=6)
        self.assertAlmostEqual(fit.base_units, 50, places=4)
        self.assertEqual(fit.base_price, 100)

    def test_noisy_sample_recovers_the_true_elasticities(self):
        fits, skipped = fit_all(SALES)
        self.assertEqual(skipped, [])
        self.assertEqual({fit.sku for fit in fits}, set(TRUE))
        for fit in fits:
            self.assertAlmostEqual(fit.elasticity, TRUE[fit.sku], delta=0.5, msg=fit.sku)
            self.assertTrue(fit.reliable, fit.sku)

    def test_range_matches_a_case_worked_out_by_hand(self):
        # log price 0..4 against log units 1,3,2,5,4: slope 0.8, residual sum 3.6,
        # variance 3.6 / 3 = 1.2, standard error sqrt(1.2 / 10), t for 3 degrees = 3.182.
        prices = [math.exp(x) for x in range(5)]
        units = [math.exp(y) for y in (1, 3, 2, 5, 4)]
        fit = fit_elasticity("x", prices, units)
        half = 3.182 * math.sqrt(0.12)
        self.assertAlmostEqual(fit.elasticity, 0.8, places=9)
        self.assertAlmostEqual(fit.std_error, math.sqrt(0.12), places=9)
        self.assertAlmostEqual(fit.low, 0.8 - half, places=9)
        self.assertAlmostEqual(fit.high, 0.8 + half, places=9)

    def test_exact_data_has_no_range(self):
        fit = fit_elasticity("x", [100, 90, 80, 70, 60], [50 * (p / 100) ** -2.5 for p in (100, 90, 80, 70, 60)])
        self.assertAlmostEqual(fit.high - fit.low, 0.0, places=6)

    def test_range_contains_the_estimate_and_narrows_with_more_weeks(self):
        fits, _ = fit_all(SALES)
        for fit in fits:
            self.assertLess(fit.low, fit.elasticity)
            self.assertGreater(fit.high, fit.elasticity)
        self.assertGreater(t_critical(3), t_critical(10))
        self.assertGreater(t_critical(30), t_critical(100))
        self.assertAlmostEqual(t_critical(100), 1.984, places=3)

    def test_a_price_that_never_moves_cannot_be_measured(self):
        with self.assertRaises(ValueError):
            fit_elasticity("flat", [100, 100, 100, 100], [10, 12, 9, 11])

    def test_too_few_weeks_is_refused(self):
        with self.assertRaises(ValueError):
            fit_elasticity("new", [100, 90], [10, 14])

    def test_weeks_with_no_sales_are_ignored(self):
        fit = fit_elasticity("x", [100, 90, 80, 70], [50, 0, 50 * 0.8 ** -2, 50 * 0.7 ** -2])
        self.assertEqual(fit.observations, 3)


class Discounts(unittest.TestCase):
    def test_no_discount_changes_nothing(self):
        self.assertEqual(units_multiplier(-3, 0), 1)
        self.assertAlmostEqual(profit_change(-3, 0.3, 0), 0)

    def test_inelastic_products_never_repay_a_discount(self):
        self.assertEqual(best_discount(-0.6, 0.3), 0)
        self.assertEqual(best_discount(-1.0, 0.3), 0)
        self.assertLess(profit_change(-0.6, 0.3, 0.1), 0)

    def test_best_discount_is_where_profit_peaks(self):
        best = best_discount(-5.5, 0.3)
        self.assertAlmostEqual(best, 0.14, places=2)
        peak = profit_change(-5.5, 0.3, best)
        self.assertGreater(peak, 0)
        self.assertGreaterEqual(peak, profit_change(-5.5, 0.3, best - 0.02))
        self.assertGreaterEqual(peak, profit_change(-5.5, 0.3, best + 0.02))

    def test_thin_margins_need_very_elastic_products(self):
        self.assertEqual(best_discount(-3.0, 0.3), 0)       # a cut earns less than it gives away
        self.assertGreater(best_discount(-3.0, 0.5), 0)     # the same product with more margin

    def test_best_discount_respects_the_ceiling(self):
        self.assertLessEqual(best_discount(-40, 0.6, max_discount=0.2), 0.2)

    def test_margin_must_be_a_share(self):
        with self.assertRaises(ValueError):
            profit_change(-3, 1.2, 0.1)


class Planning(unittest.TestCase):
    def setUp(self):
        self.fits = [fit for fit in fit_all(SALES)[0] if fit.reliable]

    def test_the_plan_stays_inside_the_budget(self):
        for budget in (500, 5_000, 50_000):
            plan = plan_budget(self.fits, budget)
            self.assertLessEqual(plan.spend, budget + 1e-6)

    def test_money_goes_to_products_that_repay_it(self):
        plan = plan_budget(self.fits, 20_000)
        by_sku = {line.sku: line for line in plan.lines}
        self.assertGreater(by_sku["fridge-family-650"].discount, 0)
        self.assertEqual(by_sku["dryer-heat-pump"].discount, 0)
        self.assertEqual(by_sku["ac-split-1.5t"].discount, 0)
        self.assertGreater(plan.extra_profit, 0)

    def test_targeting_beats_spreading_the_same_budget_evenly(self):
        plan = plan_budget(self.fits, 20_000)
        self.assertGreater(plan.extra_profit, plan.even_split_profit)

    def test_a_bigger_budget_never_earns_less(self):
        small, big = plan_budget(self.fits, 2_000), plan_budget(self.fits, 20_000)
        self.assertGreaterEqual(big.extra_profit, small.extra_profit - 1e-6)

    def test_no_budget_means_no_discounts(self):
        plan = plan_budget(self.fits, 0)
        self.assertTrue(all(line.discount == 0 for line in plan.lines))
        self.assertTrue(math.isclose(plan.extra_profit, 0, abs_tol=1e-9))


class CommandLine(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-m", "promolift.cli", *args], capture_output=True, text=True, cwd=ROOT, env={"PYTHONPATH": str(ROOT / "src")})

    def test_fit_prints_every_product(self):
        result = self.run_cli("fit", str(SALES))
        self.assertEqual(result.returncode, 0, result.stderr)
        for sku in TRUE:
            self.assertIn(sku, result.stdout)
        self.assertIn("elasticity (95% range)", result.stdout)
        self.assertRegex(result.stdout, r"-\d\.\d\d \(-\d\.\d to -\d\.\d\)")

    def test_plan_prints_the_summary(self):
        result = self.run_cli("plan", str(SALES), "--budget", "20000")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Gain from targeting", result.stdout)

    def test_a_missing_file_is_a_clean_error(self):
        result = self.run_cli("fit", "nope.csv")
        self.assertEqual(result.returncode, 2)
        self.assertIn("error:", result.stderr)


if __name__ == "__main__":
    unittest.main()
