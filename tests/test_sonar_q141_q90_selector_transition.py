import math
import unittest

from scripts.sonar_q141_q90_selector_transition import (
    transition_state, transition_features_for_target, Q80_FAMILIES, Q90_FAMILIES,
)

class Q141C6Tests(unittest.TestCase):
    def test_constant_family_has_zero_switch_and_entropy(self):
        rows = [{"selected_family": Q80_FAMILIES[0]} for _ in range(50)]
        switch, entropy, n, switches = transition_state(rows, Q80_FAMILIES)
        self.assertEqual(switch, 0.0)
        self.assertEqual(entropy, 0.0)
        self.assertEqual(n, 50)
        self.assertEqual(switches, 0)

    def test_alternating_two_families_has_unit_switch_rate(self):
        rows = [{"selected_family": Q90_FAMILIES[i % 2]} for i in range(50)]
        switch, entropy, n, switches = transition_state(rows, Q90_FAMILIES)
        self.assertEqual(switch, 1.0)
        self.assertAlmostEqual(entropy, math.log(2) / math.log(7))
        self.assertEqual(n, 50)
        self.assertEqual(switches, 49)

    def test_warmup_label_is_rejected(self):
        rows = [{"selected_family": Q80_FAMILIES[0]} for _ in range(49)]
        rows.append({"selected_family": "warmup_equal_family"})
        with self.assertRaises(RuntimeError):
            transition_state(rows, Q80_FAMILIES)

    def test_unknown_oracle_label_is_rejected(self):
        rows = [{"selected_family": Q90_FAMILIES[0]} for _ in range(49)]
        rows.append({"selected_family": "oracle_best_family_descriptive_only"})
        with self.assertRaises(RuntimeError):
            transition_state(rows, Q90_FAMILIES)

    def test_current_target_label_is_excluded(self):
        q80_rows, q90_rows = [], []
        for i in range(61):
            date = f"2020-01-{(i % 28) + 1:02d}"
            q80_rows.append({"target_index": str(i), "target_date": date, "selected_family": Q80_FAMILIES[0] if i < 60 else Q80_FAMILIES[1]})
            q90_rows.append({"prior_draws": str(i), "target_date": date, "selected_family": Q90_FAMILIES[0] if i < 60 else Q90_FAMILIES[1]})
        q7 = {"prior_draws": "60", "target_date": "2020-03-01", "cutoff_date": "2020-02-29"}
        state = transition_features_for_target(q7, q80_rows, q90_rows)
        self.assertEqual(state["q80_prior50_selector_switch_rate"], 0.0)
        self.assertEqual(state["q90_prior50_selector_switch_rate"], 0.0)
        self.assertEqual(state["q80_prior50_active_labels"], 50)
        self.assertEqual(state["q90_prior50_active_labels"], 50)
        self.assertEqual(state["q80_last_prior_target_index"], 59)
        self.assertEqual(state["q90_last_prior_draws"], 59)

    def test_noncontiguous_prior_history_fails_closed(self):
        q80_rows = [{"target_index": str(i), "target_date": "2020-01-01", "selected_family": Q80_FAMILIES[0]} for i in list(range(10)) + list(range(11, 61))]
        q90_rows = [{"prior_draws": str(i), "target_date": "2020-01-01", "selected_family": Q90_FAMILIES[0]} for i in range(61)]
        q7 = {"prior_draws": "60", "target_date": "2020-03-01", "cutoff_date": "2020-02-29"}
        with self.assertRaises(RuntimeError):
            transition_features_for_target(q7, q80_rows, q90_rows)

if __name__ == "__main__":
    unittest.main()
