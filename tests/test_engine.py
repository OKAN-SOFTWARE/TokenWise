import unittest

from tokenwise.engine import Scenario, compare_runs, estimate_tokens, inspect_prompt, simulate


class ScenarioTests(unittest.TestCase):
    def test_default_is_nonnegative_and_decreasing(self):
        result = simulate(Scenario())
        self.assertGreater(float(result["baseline_usd"]), float(result["projected_usd"]))
        self.assertEqual(len(result["waterfall"]), 4)
        self.assertEqual(result["mode"], "SIMULATION")

    def test_zero_levers_no_savings(self):
        result = simulate(Scenario(prompt_trim_pct=0, output_trim_pct=0,
                                   cache_hit_pct=0, compact_route_pct=0))
        self.assertEqual(result["savings_pct"], 0)
        self.assertEqual(result["baseline_usd"], result["projected_usd"])

    def test_positive_cache_saves_money(self):
        original = simulate(Scenario(prompt_trim_pct=0, output_trim_pct=0,
                                     cache_hit_pct=0, compact_route_pct=0))
        optimized = simulate(Scenario(prompt_trim_pct=0, output_trim_pct=0,
                                      cache_hit_pct=80, cacheable_prefix_pct=60,
                                      compact_route_pct=0))
        self.assertLess(float(optimized["projected_usd"]), float(original["projected_usd"]))

    def test_unknown_fields_rejected(self):
        with self.assertRaises(ValueError):
            Scenario.parse({"secret_rate_override": 0})

    def test_bool_and_out_of_range_rejected(self):
        for payload in ({"cache_hit_pct": True}, {"prompt_trim_pct": 1000},
                        {"requests_per_day": 0}, {"days": 367}):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                Scenario.parse(payload)

    def test_increase_traffic_scales_cost(self):
        a = simulate(Scenario(requests_per_day=1000))
        b = simulate(Scenario(requests_per_day=2000))
        self.assertAlmostEqual(float(b["baseline_usd"]), 2 * float(a["baseline_usd"]), delta=.01)

    def test_heuristic_marked(self):
        self.assertGreater(estimate_tokens("Hello world"), 0)
        report = inspect_prompt("Check this.\nCheck this.")
        self.assertEqual(report["duplicate_lines"], 1)
        self.assertIn("approximation", report["warning"].lower())


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.base = {"cost_usd": .02, "quality": 4.5, "latency_ms": 300}

    def test_saving_and_quality_pass(self):
        rows = [{"baseline": self.base,
                 "candidate": {"cost_usd": .01, "quality": 4.5, "latency_ms": 250}}] * 20
        result = compare_runs(rows)
        self.assertEqual(result["gate"], "PASS")
        self.assertEqual(result["baseline"]["p95_ms"], 300)

    def test_quality_regression_rejected_even_if_cheaper(self):
        rows = [{"baseline": self.base,
                 "candidate": {"cost_usd": .001, "quality": 2.0, "latency_ms": 100}}] * 20
        self.assertEqual(compare_runs(rows)["gate"], "REJECT")

    def test_nonfinite_rejected(self):
        rows = [{"baseline": self.base,
                 "candidate": {"cost_usd": float("nan"), "quality": 4.3, "latency_ms": 200}}]
        with self.assertRaises(ValueError):
            compare_runs(rows)


if __name__ == "__main__":
    unittest.main()
