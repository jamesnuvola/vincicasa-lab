import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import sonar_q90_expanded_formula_grammar as q90
import validate_sonar_q90_expanded_formula_grammar as validator


def test_declared_formula_count_is_exact():
    linear = {k: math.comb(20, k) for k in (4, 5, 6, 7, 8)}
    assert linear == {4: 4845, 5: 15504, 6: 38760, 7: 77520, 8: 125970}
    interaction = math.comb(20, 4) * math.comb(4, 2)
    gate = math.comb(20, 4) * 4 * 2
    assert sum(linear.values()) == 262599
    assert interaction == 29070
    assert gate == 38760
    assert sum(linear.values()) + interaction + gate == 330429


def test_feature_selection_is_discovery_only_and_family_balanced():
    families = {
        "baseline": 4,
        "cooccurrence_novelty": 4,
        "ewma_hit_dynamics": 4,
        "gap_dynamics": 4,
        "rank_trajectory": 4,
        "regime_transition_affinity": 4,
        "residual_surprise": 3,
    }
    family_by_feature = {}
    rows = []
    for family, count in families.items():
        for j in range(count):
            name = f"{family}_f{j}"
            family_by_feature[name] = family
            rows.append({
                "split": "discovery", "feature": name,
                "mean_actual_number_rank": 20.0 + j,
                "mean_number_hits_top5": 0.14 - 0.01 * j,
            })
            # These validation rows would reverse the ordering if accidentally used.
            rows.append({
                "split": "validation", "feature": name,
                "mean_actual_number_rank": 1.0 + (count - j),
                "mean_number_hits_top5": 0.9 + 0.01 * j,
            })
    selected, report = q90.select_features(rows, family_by_feature)
    assert len(selected) == 20
    expected = []
    for family, count in families.items():
        quota = 2 if family == "residual_surprise" else 3
        expected.extend(f"{family}_f{j}" for j in range(quota))
    assert set(selected) == set(expected)
    assert report["selection_split"] == "discovery"
    assert report["family_quotas"] == {
        "baseline": 3, "cooccurrence_novelty": 3, "ewma_hit_dynamics": 3,
        "gap_dynamics": 3, "rank_trajectory": 3,
        "regime_transition_affinity": 3, "residual_surprise": 2
    }


def test_rank_actuals_ties_resolve_by_number_ascending():
    scores = np.zeros((40, 3), dtype=np.float64)
    actuals = np.asarray([0, 1, 39, 20, 5], dtype=np.int16)
    ranks = q90.rank_actuals(scores, actuals)
    expected = np.asarray([1, 2, 40, 21, 6], dtype=np.int16)
    assert ranks.shape == (5, 3)
    assert np.array_equal(ranks[:, 0], expected)
    assert np.array_equal(ranks[:, 1], expected)
    assert np.array_equal(ranks[:, 2], expected)


def test_holm_adjustment_is_monotone_and_reproducible():
    p = np.asarray([0.01, 0.04, 0.03], dtype=np.float64)
    adjusted = q90.holm_adjust_array(p)
    assert np.allclose(adjusted, [0.03, 0.06, 0.06], atol=1e-12)
    assert np.all(adjusted >= p)


def test_finite_population_null_pvalues_are_bounded_near_chance():
    p5 = q90.upper_top5_hypergeometric_p(np.asarray([62], dtype=np.int64), 100)
    prank = q90.lower_mean_rank_p(np.asarray([10249], dtype=np.int64), 100)
    assert 0.4 < float(p5[0]) < 0.6
    assert 0.4 < float(prank[0]) < 0.6


def test_validator_raw_pvalue_recomputation_matches_engine():
    targets = 2008
    hits5 = np.asarray([0, 250, 251, 252, 300, 500, 1004, 2008], dtype=np.int64)
    rank_sum = np.asarray([targets * 5, targets * 40, targets * 102, targets * 103,
                           targets * 200, targets * 400, targets * 600, targets * 800],
                          dtype=np.int64)
    assert np.allclose(
        validator.upper_top5_hypergeometric_p(hits5, targets),
        q90.upper_top5_hypergeometric_p(hits5, targets),
        rtol=0.0, atol=1e-15
    )
    assert np.allclose(
        validator.lower_mean_rank_p(rank_sum, targets),
        q90.lower_mean_rank_p(rank_sum, targets),
        rtol=0.0, atol=1e-15
    )



def test_split_pvalue_arrays_are_bound_to_each_chronological_split():
    targets_by_split = {"discovery": 2008, "blind_oos": 669}
    split_names = ["discovery", "blind_oos"]
    acc = {
        "discovery": {
            "hits5": np.asarray([1348, 1255], dtype=np.int64),
            "rank_sum": np.asarray([203133, 2008 * 102], dtype=np.int64),
        },
        "blind_oos": {
            "hits5": np.asarray([400, 418], dtype=np.int64),
            "rank_sum": np.asarray([669 * 102, 669 * 103], dtype=np.int64),
        },
    }
    values = q90.compute_split_pvalue_arrays(acc, targets_by_split, split_names)

    for split in split_names:
        targets = targets_by_split[split]
        assert np.allclose(
            values[split]["p_top5"],
            q90.upper_top5_hypergeometric_p(acc[split]["hits5"], targets),
            rtol=0.0, atol=1e-15
        )
        assert np.allclose(
            values[split]["p_rank_lower"],
            q90.lower_mean_rank_p(acc[split]["rank_sum"], targets),
            rtol=0.0, atol=1e-15
        )
    assert not np.allclose(
        values["discovery"]["p_top5"], values["blind_oos"]["p_top5"], rtol=0.0, atol=1e-12
    )
    assert not np.allclose(
        values["discovery"]["p_rank_lower"], values["blind_oos"]["p_rank_lower"],
        rtol=0.0, atol=1e-12
    )



def test_validator_oracle_and_family_rank_vectors_match_emitted_ledger_schema():
    oracle_id = "L4_00_01_02_03"
    gate_id = "G4_00_01_02_03_F0_T05_B025"
    formula_map = {
        oracle_id: ("linear_mean", 4),
        gate_id: ("conditional_gate", 4),
    }
    row = {
        "oracle_best_formula_id": oracle_id,
        "oracle_best_formula_type": "linear_mean",
        "oracle_best_formula_size": "4",
        "oracle_actual_number_ranks": "[1,6,11,21,40]",
        "oracle_number_hits_top5": "1",
        "oracle_number_hits_top10": "2",
        "oracle_number_hits_top20": "3",
        "oracle_rank_sum": "79",
        "best_G4_formula_id": gate_id,
        "best_G4_formula_type": "conditional_gate",
        "best_G4_formula_size": "4",
        "best_G4_actual_number_ranks": "[2,7,12,22,39]",
        "best_G4_number_hits_top5": "1",
        "best_G4_number_hits_top10": "2",
        "best_G4_number_hits_top20": "3",
        "best_G4_rank_sum": "82",
    }
    assert validator.check_rank_vector(row, "oracle", formula_map) == (
        oracle_id, [1, 6, 11, 21, 40]
    )
    assert validator.check_rank_vector(
        row, "best_G4", formula_map, "conditional_gate", 4
    ) == (gate_id, [2, 7, 12, 22, 39])
