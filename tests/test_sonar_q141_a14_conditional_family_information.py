import unittest, sys
from pathlib import Path
import numpy as np
repo_scripts = Path(__file__).resolve().parent.parent / "scripts"
if repo_scripts.exists():
    sys.path.insert(0, str(repo_scripts))
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
import sonar_q141_a14_conditional_family_information as A14


def synthetic(n=650, seed=1414):
    rng=np.random.default_rng(seed)
    x=rng.normal(size=(n,40,59)).astype(np.float64)
    draws=np.stack([np.sort(rng.choice(np.arange(1,41),5,replace=False)) for _ in range(n)])
    y=A14.build_labels(draws)
    dates=np.asarray([f"2020-{1+(i//28):02d}-{1+(i%28):02d}" for i in range(n)])
    cutoffs=np.asarray(["2019-12-31"]+dates[:-1].tolist())
    return x,draws,y,dates,cutoffs


class ConditionalFamilyInformationTests(unittest.TestCase):
    def test_seven_families_partition_59_features(self):
        flat=[i for v in A14.FEATURE_GROUPS.values() for i in v]
        self.assertEqual(sorted(flat),list(range(59)))
        self.assertEqual(len(set(flat)),59)

    def test_exact_feature_family_mapping(self):
        names=("freq_5 freq_10 freq_20 freq_50 freq_100 freq_250 freq_500 freq_all trend_5_vs_50 trend_10_vs_100 trend_20_vs_250 age_since_hit gap_mean gap_sd overdue_ratio position_log_frequency pair_count_with_last_draw neighbor_pm1_history neighbor_pm2_history lag_1 lag_2 lag_3 lag_5 lag_10 recent_3 recent_5 recent_10 ewma_hit_hl_3 ewma_hit_hl_7 ewma_hit_hl_14 ewma_hit_hl_30 ewma_hit_hl_60 ewma_acceleration_3_14 ewma_acceleration_7_30 last_gap_vs_median last_gap_robust_z gap_cv gap_slope_recent gap_hazard_empirical gap_hazard_residual pair_lift_recent_last_draw pair_pmi_recent_last_draw cooccurrence_strength_recent cooccurrence_surprise_recent neighbor_balance_pm1_recent neighbor_balance_pm2_recent rank_velocity_5_20 rank_acceleration_5_20_50 rank_volatility_20 feature_disagreement_27 rank_consensus_27 novelty_residual_20 novelty_residual_50 regime_sum_affinity regime_span_affinity regime_parity_affinity regime_entropy_affinity transition_profile_affinity conditional_frequency_prev_draw_regime").split()
        A14.validate_feature_groups(np.asarray(names))

    def test_target_standardization_is_cross_sectional(self):
        x=np.random.default_rng(1).normal(size=(3,40,59))
        z=A14.standardize_within_target(x)
        np.testing.assert_allclose(z.mean(axis=1),0,atol=1e-12)
        np.testing.assert_allclose(z.std(axis=1),1,atol=1e-12)

    def test_zero_variance_feature_becomes_zero(self):
        x=np.random.default_rng(2).normal(size=(2,40,59))
        x[:, :, 4]=7.0
        z=A14.standardize_within_target(x)
        self.assertTrue(np.all(z[:,:,4]==0))

    def test_each_target_has_five_positive_labels(self):
        _,draws,y,_,_=synthetic()
        np.testing.assert_array_equal(y.sum(axis=1),5)
        self.assertEqual(y.shape,(650,40))

    def test_rows_outside_rolling_window_do_not_affect_target_fit(self):
        raw,draws,y,_,_=synthetic()
        x=A14.standardize_within_target(raw)
        target=500
        scores=A14.predict_scores_one_target(x,y,target)
        raw2=raw.copy(); y2=y.copy()
        rng=np.random.default_rng(44)
        raw2[:target-A14.WINDOW]=rng.normal(size=raw2[:target-A14.WINDOW].shape)
        y2[:target-A14.WINDOW]=0
        x2=A14.standardize_within_target(raw2)
        after=A14.predict_scores_one_target(x2,y2,target)
        for model in scores:
            np.testing.assert_array_equal(scores[model],after[model])

    def test_future_suffix_invariance(self):
        raw,draws,y,_,_=synthetic()
        x=A14.standardize_within_target(raw)
        target=500
        before=A14.predict_scores_one_target(x,y,target)
        raw2=raw.copy(); y2=y.copy()
        rng=np.random.default_rng(45)
        raw2[target+1:]=rng.normal(size=raw2[target+1:].shape)
        # Future labels and feature rows are deliberately changed.
        y2[target+1:]=0
        x2=A14.standardize_within_target(raw2)
        after=A14.predict_scores_one_target(x2,y2,target)
        for model in before:
            np.testing.assert_array_equal(before[model],after[model])

    def test_current_target_label_does_not_change_fitted_scores(self):
        raw,draws,y,_,_=synthetic()
        x=A14.standardize_within_target(raw)
        target=510
        before=A14.predict_scores_one_target(x,y,target)
        y2=y.copy(); y2[target]=0; y2[target,[0,1,2,3,4]]=1
        after=A14.predict_scores_one_target(x,y2,target)
        for model in before:
            np.testing.assert_array_equal(before[model],after[model])

    def test_rolling_sufficient_statistics_match_direct_reference(self):
        raw,draws,y,dates,cutoffs=synthetic()
        x=A14.standardize_within_target(raw)
        rows,_=A14.run_walk_forward(raw,draws,dates,cutoffs)
        for target in (400,401,520,649):
            ref=A14.score_one_target(x,y,target)
            row=rows[target-A14.WINDOW]
            for model,hits in ref.items():
                self.assertEqual(hits,(row[f'{model}_top5_hits'],row[f'{model}_top10_hits'],row[f'{model}_top20_hits']))

    def test_ties_resolve_to_smaller_number(self):
        scores=np.zeros(40); y=np.zeros(40); y[0]=1; y[1]=1; y[2]=1; y[3]=1; y[4]=1
        self.assertEqual(A14.ranking_hits(scores,y),(5,5,5))

    def test_cutoff_and_training_endpoints_are_strict_prior(self):
        raw,draws,y,dates,cutoffs=synthetic()
        rows,_=A14.run_walk_forward(raw,draws,dates,cutoffs)
        self.assertTrue(all(r['training_target_count']==400 for r in rows))
        self.assertTrue(all(r['training_max_index']==r['target_index']-1 for r in rows))
        self.assertTrue(all(r['cutoff_date']<r['target_date'] for r in rows))

    def test_deterministic_replay(self):
        raw,draws,y,dates,cutoffs=synthetic(n=520)
        rows1,_=A14.run_walk_forward(raw,draws,dates,cutoffs)
        rows2,_=A14.run_walk_forward(raw,draws,dates,cutoffs)
        self.assertEqual(rows1,rows2)

    def test_holm_is_monotone_and_bounded(self):
        p=[0.03,0.001,0.2,0.04]
        adj=A14.holm_adjust(p)
        self.assertTrue(all(0<=v<=1 for v in adj))
        order=np.argsort(p)
        self.assertTrue(all(adj[order[i]]<=adj[order[i+1]] for i in range(len(order)-1)))


if __name__=='__main__':
    unittest.main()
