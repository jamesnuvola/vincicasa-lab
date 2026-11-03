import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import sonar_q90_expanded_formula_grammar as q90


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
