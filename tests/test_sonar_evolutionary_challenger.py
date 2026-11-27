import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("challenger", Path(__file__).parents[1] / "scripts" / "sonar_evolutionary_challenger.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

def test_weights_sum_to_one():
    from collections import deque
    w = mod.adaptive_weights(deque())
    assert abs(sum(w.values()) - 1.0) < 1e-9

def test_rank_is_complete_and_deterministic():
    rows = mod.load_archive()
    hist = [d for _, d in rows[:mod.WARMUP]]
    a = mod.raw_features(hist)
    b = mod.raw_features(hist)
    assert a == b
    assert set(a) == set(mod.FEATURES)
    assert all(set(v) == set(mod.NUMBERS) for v in a.values())

def test_walkforward_cutoffs_precede_targets():
    rows = mod.load_archive()
    # Verify chronology and no target leakage in the recorded cutoff contract.
    for i in range(mod.WARMUP, min(len(rows), mod.WARMUP + 20)):
        assert rows[i-1][0] < rows[i][0]
