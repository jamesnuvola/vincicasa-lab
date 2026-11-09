#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path
import numpy as np
import validate_sonar_strategy_atlas_k_sensitivity as validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import sonar_strategy_atlas as q84
import sonar_strategy_atlas_k_sensitivity as sens


class Q84KSensitivityTests(unittest.TestCase):
    def synthetic_memory(self, n=80):
        rng = np.random.default_rng(84)
        states = [rng.normal(size=len(q84.FLOW_FEATURES)) for _ in range(n)]
        hits = [rng.integers(0, 6, size=len(q84.CONFIGS)).astype(float) for _ in range(n)]
        turbulence = [float(abs(rng.normal())) for _ in range(n)]
        return states, hits, turbulence

    def test_k50_reproduces_parent_q84_kernel(self):
        states, hits, turbulence = self.synthetic_memory()
        current = np.random.default_rng(85).normal(size=len(q84.FLOW_FEATURES))
        old = q84.prior_flow_context(current, states, hits, turbulence)
        new = sens.flow_context_for_k(current, states, hits, turbulence, 50)
        np.testing.assert_allclose(old[0], new[0], rtol=0, atol=1e-12)
        np.testing.assert_allclose(old[1], new[1], rtol=0, atol=1e-12)
        self.assertEqual(old[2], new[2])
        self.assertEqual(old[3], new[3])
        self.assertEqual(old[5], new[5])

    def test_narrower_neighbor_sets_are_nested(self):
        states, hits, turbulence = self.synthetic_memory()
        current = np.random.default_rng(86).normal(size=len(q84.FLOW_FEATURES))
        k10 = sens.flow_context_for_k(current, states, hits, turbulence, 10)[6]
        k20 = sens.flow_context_for_k(current, states, hits, turbulence, 20)[6]
        k50 = sens.flow_context_for_k(current, states, hits, turbulence, 50)[6]
        self.assertEqual(len(k10), 10)
        self.assertEqual(len(k20), 20)
        self.assertEqual(len(k50), 50)
        self.assertTrue(set(k10).issubset(set(k20)))
        self.assertTrue(set(k20).issubset(set(k50)))

    def test_discovery_selector_ignores_validation_and_blind_rows(self):
        rows = [
            {"strategy_id": "ENSEMBLE::FLOW_STATE_K10", "mean_hits_top20": 2.8, "mean_rank_actual_numbers": 20.1},
            {"strategy_id": "ENSEMBLE::FLOW_STATE_K20", "mean_hits_top20": 2.9, "mean_rank_actual_numbers": 20.2},
            {"strategy_id": "ENSEMBLE::FLOW_STATE_K50", "mean_hits_top20": 2.7, "mean_rank_actual_numbers": 20.0},
        ]
        k, row = sens.select_k(rows)
        self.assertEqual(k, 20)
        self.assertEqual(row["strategy_id"], "ENSEMBLE::FLOW_STATE_K20")

    def test_flow_state_is_prefix_only(self):
        history = q84.read_draws()[:240]
        a = q84.flow_state(history[:200])
        b = q84.flow_state(history[:200])
        np.testing.assert_array_equal(a, b)
        self.assertEqual(a.shape, (len(q84.FLOW_FEATURES),))
        self.assertTrue(np.isfinite(a).all())

    def test_fixed_comparator_is_not_in_inferential_family(self):
        self.assertEqual(len(sens.MODEL_IDS), 4)
        self.assertNotIn(sens.FIXED_MODEL_ID, sens.MODEL_IDS)

    def test_validator_datetime_symbols_are_imported(self):
        self.assertTrue(callable(validator.datetime.now))
        self.assertTrue(validator.timezone.utc)


if __name__ == "__main__":
    unittest.main(verbosity=2)
