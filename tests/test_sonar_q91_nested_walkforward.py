import itertools
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import sonar_per_number_condition_grammar as q80
import sonar_q91_nested_walkforward as q91


def test_q80_formula_catalog_is_exactly_3303():
    assert len(q80.FORMULAS) == 3303
    assert len(q80.FORMULA_IDS) == 3303
    assert sum(len(f) == 1 for f in q80.FORMULAS) == 27
    assert sum(len(f) == 2 for f in q80.FORMULAS) == 351
    assert sum(len(f) == 3 for f in q80.FORMULAS) == 2925
    assert len(set(q80.FORMULA_IDS)) == 3303


def test_formula_selection_has_registered_secondary_and_catalog_tiebreaks():
    hits5 = np.asarray([5, 5, 4, 5], dtype=np.int32)
    rank_sum = np.asarray([100, 90, 80, 90], dtype=np.int32)
    assert q91.select_formula(hits5, rank_sum, "top5") == 1

    hits5 = np.asarray([1, 2, 3, 4], dtype=np.int32)
    rank_sum = np.asarray([80, 80, 80, 80], dtype=np.int32)
    assert q91.select_formula(hits5, rank_sum, "rank") == 3


def test_oracle_tiebreak_matches_q80_rank_sum_top20_top5_order():
    rank_sum = np.asarray([80, 80, 80, 80, 90], dtype=np.uint16)
    hits20 = np.asarray([4, 3, 3, 3, 1], dtype=np.uint8)
    hits5 = np.asarray([1, 2, 3, 4, 5], dtype=np.uint8)
    assert q91.oracle_formula_index(rank_sum, hits5, hits20) == 3


def test_vectorized_formula_ranks_match_independent_direct_loop():
    rng = np.random.default_rng(20261105)
    standardized = rng.normal(size=(40, 27)).astype(np.float64)
    standardized[:, 0] = 0.0  # exercise stable ascending-number tie breaks
    standardized[:, 1] = 0.0
    actual_idx = np.asarray([0, 5, 12, 25, 39], dtype=np.int16)

    (actual_ranks, hits5, hits10, hits20, rank_sum,
     all5_top5, all5_top10, all5_top20) = q91.compute_target_formula_scores(
        standardized, actual_idx
    )

    expected_ranks = np.empty((5, len(q80.FORMULAS)), dtype=np.int16)
    expected_hits5 = np.empty(len(q80.FORMULAS), dtype=np.uint8)
    expected_hits10 = np.empty(len(q80.FORMULAS), dtype=np.uint8)
    expected_hits20 = np.empty(len(q80.FORMULAS), dtype=np.uint8)
    expected_rank_sum = np.empty(len(q80.FORMULAS), dtype=np.uint16)
    expected_all5_top5 = np.empty(len(q80.FORMULAS), dtype=np.uint8)
    expected_all5_top10 = np.empty(len(q80.FORMULAS), dtype=np.uint8)
    expected_all5_top20 = np.empty(len(q80.FORMULAS), dtype=np.uint8)

    for formula_index, cols in enumerate(q80.FORMULAS):
        scores = standardized[:, cols].mean(axis=1)
        order = np.lexsort((np.arange(40), -scores))
        rank = np.empty(40, dtype=np.int16)
        rank[order] = np.arange(1, 41, dtype=np.int16)
        ranks = rank[actual_idx]
        expected_ranks[:, formula_index] = ranks
        expected_hits5[formula_index] = np.sum(ranks <= 5)
        expected_hits10[formula_index] = np.sum(ranks <= 10)
        expected_hits20[formula_index] = np.sum(ranks <= 20)
        expected_rank_sum[formula_index] = np.sum(ranks)
        expected_all5_top5[formula_index] = int(np.all(ranks <= 5))
        expected_all5_top10[formula_index] = int(np.all(ranks <= 10))
        expected_all5_top20[formula_index] = int(np.all(ranks <= 20))

    assert np.array_equal(actual_ranks, expected_ranks)
    assert np.array_equal(hits5, expected_hits5)
    assert np.array_equal(hits10, expected_hits10)
    assert np.array_equal(hits20, expected_hits20)
    assert np.array_equal(rank_sum, expected_rank_sum)
    assert np.array_equal(all5_top5, expected_all5_top5)
    assert np.array_equal(all5_top10, expected_all5_top10)
    assert np.array_equal(all5_top20, expected_all5_top20)


def test_holm_adjustment_is_monotone_and_reproducible():
    p = [0.01, 0.04, 0.03]
    assert np.allclose(q91.holm_adjust(p), [0.03, 0.06, 0.06], atol=1e-12)


def test_finite_population_pvalues_are_near_chance_at_null_expectation():
    targets = 1000
    p5 = q91.upper_top5_hypergeometric_p(625, targets)
    prank = q91.lower_mean_rank_p(102500, targets)
    assert 0.4 < p5 < 0.6
    assert 0.4 < prank < 0.6


def test_rolling_window_sums_evict_oldest_formula_scores():
    queue = __import__("collections").deque()
    sum_hits5 = np.zeros(3, dtype=np.int32)
    sum_rank_sum = np.zeros(3, dtype=np.int32)
    q91.update_window(
        queue, sum_hits5, sum_rank_sum,
        np.asarray([1, 2, 3], dtype=np.uint8),
        np.asarray([50, 60, 70], dtype=np.uint16), 2
    )
    q91.update_window(
        queue, sum_hits5, sum_rank_sum,
        np.asarray([2, 1, 0], dtype=np.uint8),
        np.asarray([40, 80, 100], dtype=np.uint16), 2
    )
    q91.update_window(
        queue, sum_hits5, sum_rank_sum,
        np.asarray([0, 3, 1], dtype=np.uint8),
        np.asarray([90, 30, 20], dtype=np.uint16), 2
    )
    assert len(queue) == 2
    assert np.array_equal(sum_hits5, [2, 4, 1])
    assert np.array_equal(sum_rank_sum, [130, 110, 120])
