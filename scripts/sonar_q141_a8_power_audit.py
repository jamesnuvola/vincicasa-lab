#!/usr/bin/env python3
"""Prospective-design power audit for Q141-A8; does not read lottery outcomes."""
from __future__ import annotations
import argparse
from itertools import product
from math import comb, sqrt
from statistics import NormalDist
import json
import numpy as np

N_NUMBERS = 40
DRAW_SIZE = 5
TOP_K = 5
N_BLOCKS = 10
ALPHA_HOLM_WORST_CASE = 0.025
DEFAULT_REPLICATES = 20_000
DEFAULT_SEED = 141113

def difference_distribution(replacements: int):
    """Exact null distribution of hits(M1-only)-hits(M0-only) for fixed Top-5 sets."""
    if not isinstance(replacements, int) or not 1 <= replacements <= TOP_K:
        raise ValueError("replacements must be an integer in [1, 5]")
    counts = {}
    other = N_NUMBERS - 2 * replacements
    for a in range(replacements + 1):
        for b in range(replacements + 1):
            c = DRAW_SIZE - a - b
            if 0 <= c <= other:
                d = a - b
                counts[d] = counts.get(d, 0) + comb(replacements, a) * comb(replacements, b) * comb(other, c)
    values = np.asarray(sorted(counts), dtype=np.int16)
    raw = np.asarray([counts[int(v)] for v in values], dtype=np.float64)
    denominator = comb(N_NUMBERS, DRAW_SIZE)
    if int(raw.sum()) != denominator:
        raise AssertionError("hypergeometric counts do not sum to C(40,5)")
    return values, raw / denominator

def null_variance_hit_share(replacements: int) -> float:
    """Exact variance of (hits_M1 - hits_M0)/5 under a uniform 5-of-40 draw."""
    values, probabilities = difference_distribution(replacements)
    mean = float(np.dot(values, probabilities))
    variance_hits = float(np.dot((values - mean) ** 2, probabilities))
    return variance_hits / (TOP_K * TOP_K)

def tilted_distribution(values, null_probabilities, target_mean_hits: float):
    """Exponential-tilt sensitivity alternative with a specified mean hit difference."""
    if not -TOP_K <= target_mean_hits <= TOP_K:
        raise ValueError("target_mean_hits outside feasible range")
    if abs(target_mean_hits) < 1e-15:
        return 0.0, null_probabilities.copy()
    lo, hi = -20.0, 20.0
    for _ in range(120):
        lam = (lo + hi) / 2
        weights = null_probabilities * np.exp(lam * values)
        probabilities = weights / weights.sum()
        mean = float(np.dot(values, probabilities))
        if mean < target_mean_hits:
            lo = lam
        else:
            hi = lam
    lam = (lo + hi) / 2
    weights = null_probabilities * np.exp(lam * values)
    probabilities = weights / weights.sum()
    return lam, probabilities

def sign_patterns():
    return np.asarray(list(product((-1, 1), repeat=N_BLOCKS)), dtype=np.int8)

def simulate_block_signflip(
    replacements: int,
    active_targets: int,
    target_effect_share: float = 0.020,
    replicates: int = DEFAULT_REPLICATES,
    seed: int = DEFAULT_SEED,
    alpha: float = ALPHA_HOLM_WORST_CASE,
):
    """Monte Carlo power/type-I calibration for the preregistered 10-block sign-flip test.

    Active targets are distributed as evenly as possible over ten 20-target blocks.
    Inactive targets have zero paired difference because the Top-5 sets coincide.
    The alternative exponentially tilts the exact 5-of-40 difference distribution so
    E[(hits_M1-hits_M0)/5] equals target_effect_share on active targets. This is a
    sensitivity model, not a claim about the lottery mechanism.
    """
    if not isinstance(active_targets, int) or not 1 <= active_targets <= 200:
        raise ValueError("active_targets must be in [1, 200]")
    if replicates < 100:
        raise ValueError("replicates must be at least 100")
    if not 0 < alpha < 1:
        raise ValueError("alpha must be in (0, 1)")
    values, p0 = difference_distribution(replacements)
    target_mean_hits = TOP_K * target_effect_share
    lam, probabilities = tilted_distribution(values, p0, target_mean_hits)
    counts = [active_targets // N_BLOCKS + (b < active_targets % N_BLOCKS) for b in range(N_BLOCKS)]
    rng = np.random.default_rng(seed + 100 * replacements + active_targets + int(target_effect_share * 10000))
    blocks = np.zeros((replicates, N_BLOCKS), dtype=np.float64)
    for b, count in enumerate(counts):
        if count:
            draws = rng.choice(values, size=(replicates, count), p=probabilities)
            blocks[:, b] = draws.sum(axis=1) / TOP_K
    observed = np.abs(blocks.sum(axis=1))
    permuted = np.abs(blocks @ sign_patterns().T)
    p_values = (permuted >= observed[:, None] - 1e-12).mean(axis=1)
    rejection_rate = float(np.mean(p_values <= alpha))
    mc_se = sqrt(rejection_rate * (1 - rejection_rate) / replicates)
    return {
        "replacements": replacements,
        "active_targets": active_targets,
        "target_effect_share": target_effect_share,
        "tilt_lambda": float(lam),
        "alpha_raw": alpha,
        "replicates": replicates,
        "power_or_type1_rate": rejection_rate,
        "monte_carlo_se": mc_se,
        "active_targets_per_block": counts,
    }

def normal_approx_power(effect_share: float, active_targets: int, replacements: int, alpha: float = ALPHA_HOLM_WORST_CASE):
    sd = sqrt(null_variance_hit_share(replacements))
    zcrit = NormalDist().inv_cdf(1 - alpha / 2)
    z = effect_share * sqrt(active_targets) / sd
    normal = NormalDist()
    return normal.cdf(-zcrit - z) + 1 - normal.cdf(zcrit - z)

def normal_approx_n80(effect_share: float, replacements: int, alpha: float = ALPHA_HOLM_WORST_CASE):
    sd = sqrt(null_variance_hit_share(replacements))
    zcrit = NormalDist().inv_cdf(1 - alpha / 2)
    z80 = NormalDist().inv_cdf(0.80)
    return ((zcrit + z80) * sd / effect_share) ** 2

def run_audit(replicates: int = DEFAULT_REPLICATES, seed: int = DEFAULT_SEED):
    scenarios = []
    for m in range(1, 6):
        for q in (50, 200):
            alt = simulate_block_signflip(m, q, 0.020, replicates, seed)
            null = simulate_block_signflip(m, q, 0.0, replicates, seed)
            scenarios.append({
                **alt,
                "null_type1_rate": null["power_or_type1_rate"],
                "null_type1_mc_se": null["monte_carlo_se"],
                "normal_approx_power": normal_approx_power(0.020, q, m),
                "normal_approx_active_n_for_80pct": normal_approx_n80(0.020, m),
            })
    return {
        "schema_version": "1.0",
        "task_id": "Q141-A8-POWER-AUDIT",
        "status": "COMPLETED_DESIGN_SIMULATION_NOT_PREDICTIVE_TEST",
        "design": {
            "population": "uniform 5-of-40 combinatorial null",
            "top_k": 5,
            "numbers": 40,
            "targets_total": 200,
            "divergence_active_scenarios": [50, 200],
            "blocks": 10,
            "targets_per_block": 20,
            "sign_flip_configurations": 1024,
            "holm_worst_case_raw_alpha": ALPHA_HOLM_WORST_CASE,
            "conditional_effect_share": 0.020,
            "implied_expected_hit_difference": 0.1,
            "replicates_per_scenario": replicates,
            "seed": seed,
            "alternative": "exponential tilt of the exact 5-of-40 subset distribution by exp(lambda * (hits_M1_only - hits_M0_only)); lambda is solved to yield +0.020 paired Top-5 hit share on active targets",
            "active_targets_evenly_distributed_across_blocks": True,
        },
        "scenarios": scenarios,
        "limitations": [
            "This is design power analysis only; it does not use historical or prospective draw outcomes.",
            "The exponential-tilt alternative is a sensitivity model, not an assertion about the lottery mechanism.",
            "Power depends on the actual divergence-size distribution and serial dependence.",
            "The block sign-flip test has only ten block-level sign units; the reported Monte Carlo power is conditional on the stated block design.",
            "No B11 outcome is read, appended, or used to tune A8.",
        ],
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--replicates", type=int, default=DEFAULT_REPLICATES)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args()
    print(json.dumps(run_audit(args.replicates, args.seed), indent=2, sort_keys=True))

if __name__ == "__main__":
    main()
