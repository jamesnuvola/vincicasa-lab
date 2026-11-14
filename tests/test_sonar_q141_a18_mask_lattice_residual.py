import unittest
import numpy as np

from sonar_q141_a17_full_universe_spectral import fit_basis
from sonar_q141_a18_mask_lattice_residual import (
    build_mask_design,
    conditional_shift_surrogates,
    fit_split_models,
    residual_orthogonality_error,
    residualize_rows,
    split_training_window,
    subspace_overlap,
)
from sonar_q141_a17_full_universe_spectral import split_slices

class Q141A18Tests(unittest.TestCase):
    def test_full_mask_design_has_56_independent_columns(self):
        formulas = [{"formula_mask": i, "feature_count": int(i.bit_count())} for i in range(1, 1024)]
        design, q, meta = build_mask_design(formulas)
        self.assertEqual(design.shape, (1023, 56))
        self.assertEqual(meta["design_rank"], 56)
        self.assertEqual(meta["residual_degrees_of_freedom"], 967)
        np.testing.assert_allclose(q.T @ q, np.eye(56), atol=1e-11)

    def test_mask_design_rejects_missing_or_reordered_masks(self):
        formulas = [{"formula_mask": i, "feature_count": int(i.bit_count())} for i in range(1, 1024)]
        formulas[4], formulas[5] = formulas[5], formulas[4]
        with self.assertRaises(ValueError):
            build_mask_design(formulas)

    def test_residuals_are_orthogonal_to_intercept_main_and_pair_design(self):
        formulas = [{"formula_mask": i, "feature_count": int(i.bit_count())} for i in range(1, 1024)]
        _, q, _ = build_mask_design(formulas)
        rng = np.random.default_rng(181)
        x = rng.normal(size=(12, 1023))
        residual = residualize_rows(x, q)
        self.assertLess(residual_orthogonality_error(residual, q), 1e-11)
        np.testing.assert_allclose(residual.mean(axis=1), 0.0, atol=1e-11)

    def test_projection_of_design_space_vector_is_zero(self):
        formulas = [{"formula_mask": i, "feature_count": int(i.bit_count())} for i in range(1, 1024)]
        design, q, _ = build_mask_design(formulas)
        coefficients = np.arange(56, dtype=np.float64)
        x = (design @ coefficients).reshape(1, -1)
        residual = residualize_rows(x, q)
        self.assertLess(float(np.max(np.abs(residual))), 1e-10)

    def test_training_windows_are_immediately_prior_and_fixed_length(self):
        ranges = split_slices(2986)
        expected = {
            "discovery": (0, 400, 400, 2192),
            "validation": (1792, 2192, 2192, 2789),
            "blind_oos": (2389, 2789, 2789, 3386),
        }
        for name, sl in ranges.items():
            train = split_training_window(sl, 400)
            self.assertEqual((train.start, train.stop, sl.start, sl.stop), expected[name])
            self.assertEqual(train.stop, sl.start)
            self.assertEqual(train.stop - train.start, 400)

    def test_subspace_overlap_bounds(self):
        rng = np.random.default_rng(182)
        q, _ = np.linalg.qr(rng.normal(size=(30, 6)))
        self.assertAlmostEqual(subspace_overlap(q, q), 1.0, places=12)
        other, _ = np.linalg.qr(rng.normal(size=(30, 6)))
        value = subspace_overlap(q, other)
        self.assertGreaterEqual(value, 0.0)
        self.assertLessEqual(value, 1.0)

    def test_conditional_shift_null_is_deterministic_and_bounded(self):
        rng = np.random.default_rng(183)
        formulas = [{"formula_mask": i, "feature_count": int(i.bit_count())} for i in range(1, 1024)]
        _, q, _ = build_mask_design(formulas)
        x = residualize_rows(rng.normal(size=(430, 1023)), q)
        ranges = {"discovery": slice(400, 412), "validation": slice(412, 420), "blind_oos": slice(420, 430)}
        a = conditional_shift_surrogates(x, q, ranges, replicates=2, seed=184)
        b = conditional_shift_surrogates(x, q, ranges, replicates=2, seed=184)
        for name in ranges:
            np.testing.assert_array_equal(a[name], b[name])
            self.assertEqual(a[name].shape, (2,))
            self.assertTrue(np.all((a[name] >= 0.0) & (a[name] <= 1.0)))

    def test_split_model_uses_prior_window_for_each_basis(self):
        rng = np.random.default_rng(185)
        raw = rng.normal(size=(430, 32))
        residual = rng.normal(size=(430, 32))
        ranges = {"discovery": slice(400, 412), "validation": slice(412, 420), "blind_oos": slice(420, 430)}
        models = fit_split_models(residual, raw, ranges)
        for name, model in models.items():
            self.assertEqual(model["train_slice"].stop, model["target_slice"].start)
            self.assertEqual(model["training_rows"], 400)
            self.assertEqual(len(model["captures"]), model["target_slice"].stop - model["target_slice"].start)
            self.assertTrue(np.all((model["captures"] >= 0.0) & (model["captures"] <= 1.0)))

    def test_future_suffix_does_not_change_discovery_training_basis(self):
        rng = np.random.default_rng(186)
        x = rng.normal(size=(430, 32))
        q, _ = np.linalg.qr(rng.normal(size=(32, 8)))
        residual1 = x[:400] - (x[:400] @ q) @ q.T
        basis1, _ = fit_basis(residual1, 6)
        suffix = x.copy()
        suffix[400:] = rng.normal(loc=100.0, size=suffix[400:].shape)
        residual2 = suffix[:400] - (suffix[:400] @ q) @ q.T
        basis2, _ = fit_basis(residual2, 6)
        np.testing.assert_array_equal(basis1, basis2)

    def test_circular_shift_preserves_column_circular_autocorrelation(self):
        rng = np.random.default_rng(187)
        x = rng.normal(size=(100, 7))
        shifts = rng.integers(1, 100, size=7)
        shifted = np.empty_like(x)
        for j, shift in enumerate(shifts):
            shifted[:, j] = np.roll(x[:, j], int(shift))
        for j in range(x.shape[1]):
            for lag in range(10):
                a = np.dot(x[:, j], np.roll(x[:, j], lag))
                b = np.dot(shifted[:, j], np.roll(shifted[:, j], lag))
                self.assertAlmostEqual(float(a), float(b), places=9)

    def test_residual_projection_is_idempotent(self):
        formulas = [{"formula_mask": i, "feature_count": int(i.bit_count())} for i in range(1, 1024)]
        _, q, _ = build_mask_design(formulas)
        rng = np.random.default_rng(188)
        x = rng.normal(size=(5, 1023))
        r1 = residualize_rows(x, q)
        r2 = residualize_rows(r1, q)
        np.testing.assert_allclose(r1, r2, atol=1e-11)

    def test_target_count_and_split_counts_match_a17_panel(self):
        ranges = split_slices(2986)
        self.assertEqual({k: v.stop-v.start for k,v in ranges.items()},
                         {"discovery":1792,"validation":597,"blind_oos":597})
        self.assertEqual(ranges["blind_oos"].stop, 3386)

    def test_residual_degrees_of_freedom_are_correct(self):
        self.assertEqual(1023 - (1 + 10 + 45), 967)

if __name__ == "__main__":
    unittest.main()
