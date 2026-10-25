#!/usr/bin/env python3
"""Regression tests for exhaustive SONAR formula catalog invariants."""
from __future__ import annotations

import itertools
import math
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import sonar_exhaustive_formula_lab as lab  # noqa: E402


class ExhaustiveFormulaLabTests(unittest.TestCase):
    def test_complete_candidate_universe_size(self):
        self.assertEqual(math.comb(40, 5), 658008)
        self.assertEqual(lab.EXPECTED_CANDIDATES, 658008)

    def test_colex_rank_is_unique_for_every_quintet(self):
        ranks = [lab.colex_rank(combo) for combo in itertools.combinations(range(1, 41), 5)]
        self.assertEqual(len(ranks), 658008)
        self.assertEqual(len(set(ranks)), 658008)
        self.assertEqual(min(ranks), 0)
        self.assertEqual(max(ranks), 658007)

    def test_gray_code_covers_every_nonempty_formula_mask(self):
        masks = [i ^ (i >> 1) for i in range(1, 1 << len(lab.FAMILY_NAMES))]
        self.assertEqual(len(masks), 1023)
        self.assertEqual(set(masks), set(range(1, 1024)))

    def test_top20_ties_are_stable_and_lexicographic(self):
        chosen = lab.top_indices(np.ones(100, dtype=np.float64), 20)
        self.assertEqual(chosen.tolist(), list(range(20)))

    def test_top_indices_rank_highest_scores_first(self):
        scores = np.array([0.1, 0.9, 0.5, 0.8, 0.2])
        self.assertEqual(lab.top_indices(scores, 3).tolist(), [1, 3, 2])

    def test_each_historical_target_uses_only_prior_draws(self):
        dates = ["2026-01-01", "2026-01-02", "2026-01-03"]
        draws = [(1, 2, 3, 4, 5), (2, 4, 6, 8, 10), (1, 2, 3, 4, 5)]
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            with patch.object(lab, "OUT", temp_path), patch.object(lab, "LEDGER", temp_path / "ledger.csv"):
                state = lab.build_condition_ledger(dates, draws)
            rows = state["rows"]
            self.assertEqual(len(rows), 3)
            self.assertEqual(rows[0]["prior_draws"], 0)
            self.assertEqual(rows[0]["cutoff_date"], "")
            self.assertEqual(rows[0]["prior_exact_quintet_count"], 0)
            self.assertEqual(rows[1]["prior_draws"], 1)
            self.assertEqual(rows[1]["cutoff_date"], "2026-01-01")
            self.assertEqual(rows[1]["prior_exact_quintet_count"], 0)
            self.assertEqual(rows[2]["prior_draws"], 2)
            self.assertEqual(rows[2]["cutoff_date"], "2026-01-02")
            self.assertEqual(rows[2]["prior_exact_quintet_count"], 1)

    def test_research_output_is_separate_from_immutable_freezes(self):
        self.assertEqual(lab.REPORT.name, "exhaustive_formula_catalog.json")
        self.assertEqual(lab.LEDGER.name, "exhaustive_formula_condition_ledger.csv")
        self.assertNotIn("freeze", str(lab.REPORT).lower())
        self.assertNotIn("freeze", str(lab.LEDGER).lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
