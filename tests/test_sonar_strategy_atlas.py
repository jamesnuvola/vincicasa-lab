#!/usr/bin/env python3
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import sonar_strategy_atlas as q84


class Q84FlowStateTests(unittest.TestCase):
    def synthetic_history(self, n=240):
        rows = []
        start = date(2025, 1, 1)
        for i in range(n):
            base = (i * 7) % 36 + 1
            nums = sorted({((base + j * 7 - 1) % 40) + 1 for j in range(5)})
            while len(nums) < 5:
                nums.append((nums[-1] % 40) + 1)
                nums = sorted(set(nums))
            rows.append({"date": start + timedelta(days=i), "nums": tuple(nums)})
        return rows

    def test_flow_state_uses_only_supplied_prefix(self):
        history = self.synthetic_history()
        a = q84.flow_state(history[:200])
        future = self.synthetic_history(30)
        b = q84.flow_state(history[:200])
        self.assertEqual(a.shape, (13,))
        np.testing.assert_array_equal(a, b)
        self.assertTrue(np.isfinite(a).all())

    def test_flow_state_rejects_short_prefix(self):
        with self.assertRaises(ValueError):
            q84.flow_state(self.synthetic_history(99))

    def test_prior_flow_context_is_deterministic_and_prior_only(self):
        states = [q84.flow_state(self.synthetic_history(200 + i)) for i in range(40)]
        hits = [np.full(42, 2.5 + (i % 3) * 0.1) for i in range(40)]
        turb = [float(i % 7) for i in range(40)]
        current = q84.flow_state(self.synthetic_history(260))
        a = q84.prior_flow_context(current, states, hits, turb)
        b = q84.prior_flow_context(current, states, hits, turb)
        np.testing.assert_allclose(a[0], b[0])
        np.testing.assert_allclose(a[1], b[1])
        self.assertEqual(a[2], 40)
        self.assertTrue(0.5 <= float(a[0].min()) <= float(a[0].max()) <= 2.0)

    def test_rank_vector_is_complete_permutation(self):
        ranks = q84.rank_vector_from_order(list(range(1, 41)))
        self.assertEqual(sorted(ranks.tolist()), list(range(1, 41)))
        with self.assertRaises(ValueError):
            q84.rank_vector_from_order([1] * 40)

    def test_conditional_hypergeometric_screen_is_bounded(self):
        p = q84.hypergeom_screen_p(250, 100, 20)
        self.assertTrue(0.0 <= p <= 1.0)
        self.assertGreater(q84.hypergeom_screen_p(220, 100, 20),
                           q84.hypergeom_screen_p(300, 100, 20))

    def test_holm_adjustment_is_monotone_and_bounded(self):
        items = [
            {"test_id": "a", "p_raw": 0.001},
            {"test_id": "b", "p_raw": 0.02},
            {"test_id": "c", "p_raw": 0.5},
        ]
        adjusted = q84.holm_adjust(items)
        self.assertTrue(all(0 <= x <= 1 for x in adjusted.values()))
        self.assertGreaterEqual(adjusted["a"], 0.001)
        self.assertGreaterEqual(adjusted["b"], adjusted["a"])
        self.assertGreaterEqual(adjusted["c"], adjusted["b"])

    def test_split_dimensions_are_chronological(self):
        total = 3202
        self.assertEqual(sum(q84.split_name(i, total) == "discovery" for i in range(total)), 1921)
        self.assertEqual(sum(q84.split_name(i, total) == "validation" for i in range(total)), 640)
        self.assertEqual(sum(q84.split_name(i, total) == "blind_oos" for i in range(total)), 641)

    def test_block_bootstrap_is_reproducible(self):
        a = np.arange(100, dtype=float) / 100
        b = np.zeros(100, dtype=float)
        x = q84.bootstrap_paired(a, b, 84)
        y = q84.bootstrap_paired(a, b, 84)
        self.assertEqual(x, y)
        self.assertLess(x["ci95"][0], x["ci95"][1])


if __name__ == "__main__":
    unittest.main(verbosity=2)
