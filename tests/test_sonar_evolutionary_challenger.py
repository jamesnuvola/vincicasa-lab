import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("challenger", Path(__file__).parents[1] / "scripts" / "sonar_evolutionary_challenger.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class ChallengerTests(unittest.TestCase):
    def test_weights_sum_to_one(self):
        from collections import deque
        w = mod.adaptive_weights(deque())
        self.assertAlmostEqual(sum(w.values()), 1.0, places=9)
        self.assertEqual(len(w), 28)

    def test_rank_is_complete_and_deterministic(self):
        rows = mod.load_archive()
        hist = [d for _, d in rows[:mod.WARMUP]]
        a = mod.raw_features(hist)
        b = mod.raw_features(hist)
        self.assertEqual(a, b)
        self.assertEqual(set(a), set(mod.FEATURES))
        self.assertTrue(all(set(v) == set(mod.NUMBERS) for v in a.values()))

    def test_champion_replica_matches_frozen_current_ranking(self):
        rows = mod.load_archive()
        stay, out = [0]*41, [0]*41
        draws = [d for _,d in rows]
        for j in range(len(draws)-1):
            mod.update_transition(stay,out,draws[j],draws[j+1])
        self.assertEqual(mod.champion_rank(draws,stay,out)[:5], [25,16,38,26,3])

    def test_flow_residual_state_dimensions(self):
        rows = mod.load_archive()
        hist = [d for _, d in rows[:mod.WARMUP]]
        self.assertEqual(len(mod.structural_state(hist)), 25)

    def test_paired_bootstrap_is_deterministic(self):
        sample = [
            {"top5":[1],"champion_top5":[2],"actual":[1]},
            {"top5":[1],"champion_top5":[2],"actual":[1]},
            {"top5":[1],"champion_top5":[2],"actual":[1]},
            {"top5":[1],"champion_top5":[2],"actual":[1]},
        ]
        result = mod.paired_block_bootstrap(sample,"top5","champion_top5",block_length=2,replicates=100)
        self.assertEqual(result["mean_delta"],1.0)
        self.assertEqual(result["ci95"],[1.0,1.0])

    def test_walkforward_uses_only_prior_cutoff(self):
        rows = mod.load_archive()
        result = mod.run(rows[:mod.WARMUP + 12])
        self.assertEqual(len(result["ledger"]), 12)
        for row in result["ledger"]:
            self.assertLess(row["history_cutoff"], row["target_date"])
            self.assertGreaterEqual(row["history_draws"], mod.WARMUP)

if __name__ == "__main__":
    unittest.main()
